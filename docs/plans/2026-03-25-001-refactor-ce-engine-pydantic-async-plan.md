---
title: refactor: ce_engine Python-first Pydantic async rewrite
type: refactor
status: completed
date: 2026-03-25
origin: docs/brainstorms/2026-03-25-ce-engine-pydantic-async-requirements.md
---

# refactor: ce_engine Python-first Pydantic async rewrite

## Enhancement Summary

**Deepened on:** 2026-03-25
**Sections enhanced:** All sections
**Research agents used:** kieran-python-reviewer, architecture-strategist, performance-oracle, code-simplicity-reviewer, best-practices-researcher, framework-docs-researcher

### Key Improvements from Research

1. **Critical fix: `anyio.run_process` has no built-in `timeout` param** -- must wrap with `anyio.fail_after()` cancel scope
2. **Concurrent ruff + ty in `prefetch_node`** -- run lint checks in parallel via `anyio.TaskGroup` for 30-50% subprocess time reduction
3. **Drop `IntentKind` type alias** -- inlined `Literal` is sufficient; type alias adds no behavior
4. **Reduce test scope to 3 focused modules** -- `test_state`, `test_graph`, `test_nodes`; cut `test_config`, `test_prompts`, `test_toolchain` as YAGNI
5. **Remove stale problem claim** -- `tenacity` is already in `pyproject.toml`; remove from Problem Statement
6. **Drop `run_git_command`** -- thin wrapper that adds no value over `run_command`
7. **Concurrent prefetch optimization** added as explicit item

---

## Overview

Refactor `ce_engine/` from TypeScript-to-Python migration state (TypedDict + sync) to idiomatic Python 3.13 with Pydantic v2 state models and `anyio` async nodes.

## Problem Statement

The `ce_engine/` code (634 lines, 5 modules) was ported from TypeScript but not fully modernized:

- `TypedDict` + `cast()` throughout -- no Pydantic validation on LLM JSON output, no defaults
- Sync-only code despite `anyio` being declared a dependency
- Three nodes duplicate the same `ruff check --output-format=json` subprocess call
- `pydantic-settings` in deps but never used -- config is hardcoded
- LLM JSON output parsed with `json.loads` then `cast()` -- malformed output silently propagates bad state

The code works but is not safe to build on top of in its current form.

## Proposed Solution

### 1. Replace State Models with Pydantic BaseModel

Replace `state.py` TypedDict classes with Pydantic `BaseModel`:

- `WorkState(BaseModel)` -- validated fields with defaults, attribute access instead of dict access
- `WorkIntent(BaseModel)` -- `Literal` intent field with Pydantic validation (no `cast()` needed)
- `RuffError(BaseModel)` -- `extra="allow"` for forward-compat with ruff JSON output
- `make_continue_intent()` factory replaces mutable `_EMPTY_INTENT` dict

**Research note:** LangGraph natively supports `StateGraph(WorkState)` with `BaseModel` -- no `cast(Any, WorkState)` workaround needed. Nodes continue returning plain `dict`; LangGraph coerces automatically.

**Simplification:** Do NOT add a `type IntentKind = Literal[...]` alias. The inlined `Literal` in `WorkIntent.intent` provides identical type safety without the indirection.

### 2. Add Centralized Configuration

Create `config.py` with `EngineSettings(BaseSettings)`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CE_",
        env_file=".env",
        extra="ignore",  # catches CE_ env var typos at startup
    )
    model_name: str = "claude-sonnet-4-20250514"
    max_iterations: int = 5
    tool_call_budget: int = 10
    lint_timeout: float = 30.0
    pytest_timeout: float = 120.0
    context_pack_path: Path = Path(".context/compound-engineering/context-pack.md")
    learnings_path: Path = Path(".context/compound-engineering/learnings")
    plan_gaps_path: Path = Path(".context/compound-engineering/plan-gaps.md")

settings = EngineSettings()
```

**Required:** `extra="ignore"` (NOT `extra="forbid"`) on `EngineSettings`. The `python-antipatterns` skill specifies `extra="forbid"` only for settings that control environment validation -- `EngineSettings` reads `CE_*` env vars for runtime config, so `extra="ignore"` is correct here.

### 3. Extract DRY Toolchain Module

Create `toolchain.py` with shared subprocess runners:

```python
import anyio
from dataclasses import dataclass

@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

async def run_command(cmd: list[str], timeout: float = 30.0) -> CommandResult:
    """Run a command with timeout via anyio.fail_after cancel scope."""
    try:
        with anyio.fail_after(timeout):
            result = await anyio.run_process(cmd)
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout.decode(),
                stderr=result.stderr.decode(),
            )
    except anyio.TimeoutError:
        return CommandResult(returncode=124, stdout="", stderr="Command timed out")
```

**Critical:** `anyio.run_process` has NO built-in `timeout` parameter. The timeout MUST be implemented via `anyio.fail_after()` cancel scope wrapper.

Functions in `toolchain.py`:
- `run_ruff_check()` -- calls ruff, returns `list[RuffError]`
- `run_ty_check()` -- calls ty, returns trimmed output string
- `run_pytest()` -- calls pytest, returns `(returncode, stdout, stderr)`
- `compute_error_delta(baseline, current)` -- pure function, returns delta string

**Drop `run_git_command`** -- a thin wrapper over `run_command` that adds no value.

### 4. Concurrent Prefetch Optimization

In `prefetch_node`, run `ruff check` and `ty check` concurrently via `anyio.TaskGroup`:

```python
async def prefetch_node(state: WorkState) -> dict:
    async with anyio.create_task_group() as tg:
        tg.start_soon(_run_ruff_async)
        tg.start_soon(_run_ty_async)
    # both complete here; max(ruff_time, ty_time) vs sequential sum
```

This cuts `prefetch_node` subprocess wall-clock time by 30-50%.

### 5. Convert Nodes to Async

Replace all 7 node functions in `nodes.py` with `async def`:

- All nodes use `anyio.run_process()` wrapped in `anyio.fail_after()` for timeout
- Singleton `_llm = ChatAnthropic(...)` created once at module level (not per-call -- the current per-call instantiation loses connection pool on every retry)
- `_parse_intent()` scans backwards through LLM output lines until JSON is found
- Nodes return plain `dict` -- LangGraph merges into state automatically, no `cast()`
- `validate_node` no longer overwrites `task_description` on test failure

### 6. Update Remaining Modules

- `graph.py` -- `StateGraph(WorkState)` directly (no `cast(Any, WorkState)`), Pydantic attribute access in routing functions
- `cli.py` -- `CliInput(BaseModel)` for argument validation, `anyio.run()` for async entry point, `graph.ainvoke()` instead of sync `graph.invoke()`
- `prompts.py` -- attribute access (`state.task_description`) instead of dict access
- `__init__.py` -- public API exports: `WorkState`, `WorkIntent`, `build_work_graph`, `settings`

### 7. Add Tests

Create `ce_engine/tests/` with **3** focused test modules (reduced from 6 per simplification review):

- `tests/__init__.py` -- empty
- `tests/conftest.py` -- `monkeypatch` env var overrides for settings isolation
- `tests/test_state.py` -- Pydantic model validation, intent factory, serialization roundtrip
- `tests/test_graph.py` -- routing logic (pure functions, no LLM calls)
- `tests/test_nodes.py` -- intent parsing from LLM output, CLI input validation

**Dropped (YAGNI):** `test_config.py` (EngineSettings is simple dataclass-like; basic import test suffices), `test_prompts.py` (33-line pure string formatting function), `test_toolchain.py` (tests new code with no current callers beyond what nodes already cover).

### 8. Fix Release Config

Verify and fix stale release-please config files if needed. The current `release-please-config.json` does NOT reference `package.json` or `.cursor-plugin` -- verify before modifying.

### 9. Fix README

Update root `README.md` stack table to reflect actual `ce_engine/` dependencies.

## Acceptance Criteria

- [ ] `uv sync` resolves all dependencies without warnings
- [ ] `uv run ruff check src/ tests/` passes with zero errors
- [ ] `uv run ruff format --check src/ tests/` passes
- [ ] `uv run ty check src/` passes with zero errors
- [ ] `uv run pytest -v` -- all tests pass
- [ ] `uv run ce-work --help` prints usage without ImportError
- [ ] `from ce_engine import WorkState, build_work_graph, settings` imports successfully

## File Inventory

**Replaced (8 files):**

| File | Key change |
|---|---|
| `ce_engine/pyproject.toml` | Tool config sections (deps already present) |
| `ce_engine/src/ce_engine/__init__.py` | Public API exports |
| `ce_engine/src/ce_engine/cli.py` | Async entry, Pydantic `CliInput`, `anyio.run()` |
| `ce_engine/src/ce_engine/graph.py` | `StateGraph(WorkState)` direct, attribute access |
| `ce_engine/src/ce_engine/nodes.py` | `async def` nodes, singleton LLM, DRY toolchain |
| `ce_engine/src/ce_engine/prompts.py` | Attribute access |
| `ce_engine/src/ce_engine/state.py` | Pydantic `BaseModel` classes |
| `README.md` | Accurate stack table |

**New (2 files):**

| File | Purpose |
|---|---|
| `ce_engine/src/ce_engine/config.py` | `EngineSettings(BaseSettings)` with `anyio.fail_after` timeout pattern |
| `ce_engine/src/ce_engine/toolchain.py` | Async subprocess runners with proper timeout via cancel scope |
| `.github/release-please-config.json` | Fix only if stale references found |
| `.github/.release-please-manifest.json` | Fix only if stale references found |

**New tests (3 files):**

| File | Coverage |
|---|---|
| `ce_engine/tests/__init__.py` | Empty |
| `ce_engine/tests/conftest.py` | Env var override fixtures |
| `ce_engine/tests/test_state.py` | State model validation |
| `ce_engine/tests/test_graph.py` | Routing functions |
| `ce_engine/tests/test_nodes.py` | Intent parsing |

## Commit Strategy

Two commits on branch `refactor/ce-engine-pydantic-async`:

**Commit 1** -- config + release files (Steps 2, 7 if needed):
```
fix: add EngineSettings config module, verify release-please config
```

**Commit 2** -- code refactor + tests (Steps 1, 3-6, 8-9):
```
refactor: migrate ce_engine to Pydantic v2 state, async nodes, DRY toolchain

- Replace TypedDict state with Pydantic BaseModel (WorkState, WorkIntent, RuffError)
- Add EngineSettings(BaseSettings) for centralized CE_* env var configuration
- Extract toolchain module with anyio.fail_after(timeout) subprocess pattern
- Convert all 7 graph nodes to async def; singleton LLM client at module level
- Run ruff + ty concurrently in prefetch_node via anyio.TaskGroup
- Backward-scanning intent parser with Pydantic validation
- Add 3 test modules covering state models, graph routing, and intent parsing
- Fix README stack table accuracy
```

## Dependencies & Risks

- **Critical:** `anyio.run_process(timeout=...)` does NOT work -- must use `anyio.fail_after()` cancel scope wrapper. This is a common mistake.
- **Risk:** `anyio.run_process` sends `SIGTERM` to the process group on timeout (via `killpg`), which differs from `subprocess.run` single-process signal behavior. For ruff/ty/pytest (no child processes), this is safe.
- **Risk:** `ChatAnthropic` singleton must not be used with parallel node execution -- document this constraint.
- **Assumption:** `langgraph>=1.1.3` supports `StateGraph(BaseModel)` and `ainvoke()` natively (confirmed).
- **Assumption:** `anyio>=4.13.0` supports `fail_after()` and `run_process()` as used here (confirmed).

## Verification Commands

```bash
cd ce_engine

# Dependencies resolve
uv sync

# Lint + format
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run ty check src/

# Tests
uv run pytest -v

# CLI entry point
uv run ce-work 2>&1 | head -5
```

## Sources

- **Research:** LangGraph async + Pydantic state (framework-docs-researcher) -- `StateGraph(WorkState)` works natively
- **Research:** anyio subprocess timeout pattern (best-practices-researcher) -- must use `anyio.fail_after()` cancel scope
- **Research:** Simplification review (code-simplicity-reviewer) -- drop IntentKind alias, reduce test files
- **Research:** Performance review (performance-oracle) -- concurrent ruff+ty is biggest win; singleton LLM fixes existing connection pool bug
- **Research:** Architecture review (architecture-strategist) -- interrupt values bypass state model; no changes needed
- **Existing patterns:** docs/solutions/code-quality/python-engine-review-patterns.md
