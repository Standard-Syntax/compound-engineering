---
title: "refactor: ce_engine post-migration cleanup"
type: refactor
status: completed
date: 2026-03-25
origin: code review of current ce_engine/ after Pydantic v2 migration
deepened: true
---

# refactor: ce_engine post-migration cleanup

## Enhancement Summary

**Deepened on:** 2026-03-25
**Research agents used:** kieran-python-reviewer, code-simplicity-reviewer, architecture-strategist, pattern-recognition-specialist, performance-oracle
**Learnings applied:** `docs/solutions/logic-errors/async-baseexception-re-raise-pattern.md`, `docs/solutions/code-quality/python-engine-review-patterns.md`

### Key Improvements from Deepening

1. **Work Item 3 re-scoped**: The "mixed async frameworks" characterization is overstated — `asyncio` is used in only one place (toolchain.py line 47, for `CancelledError`). The change is valid but minor. The plan should call this out explicitly rather than implying widespread framework mixing.

2. **Work Item 4 — `functools.cache` preferred over holder pattern**: The python-engine-review-patterns learning notes that `functools.cache` makes the cached value immutable after first call, which is more aligned with the connection-pool-preservation intent than a mutable holder class. The holder pattern is an improvement over `global`, but `functools.cache` is cleaner still.

3. **Work Item 5 — most architecturally significant**: Confirmed by all reviewers. The `"tests failed" in state.error_delta.lower()` string matching in `graph.py:57` is a leaky abstraction — routing logic silently breaks if the error message wording changes. The `tests_passed: bool` field is the correct fix.

4. **Work Item 6 — validate_node is on the hot path**: performance-oracle analysis confirms `validate_node` runs sequentially (lines 302-303 in current code), wasting ~43% of wall-clock time per lint pass. The extraction to `_run_lint_checks()` will benefit every LLM iteration. error_compact_node already runs concurrent — the plan's description of it as "sequential" was outdated.

5. **Work Item 7 — test bugs discovered**: The architecture-strategist review reveals that `test_nodes.py` tests `test_no_json_returns_continue` and `test_empty_output_returns_continue` have incorrect expectations — they expect `"continue"` but `nodes.py:77-78` defaults to `"blocked"` when parsing fails. These tests need to expect `"blocked"`. Additionally, the mock at `test_nodes.py:113` returns `b""` (bytes) but `CommandResult` declares `stdout: str` — a latent type bug.

6. **Missing: prefetch_node return type annotation**: `nodes.py` line 81 returns `dict` but should be `dict[str, Any]`. This is not in the original plan and should be added.

---

## Overview

The `ce_engine/` code was recently migrated from TypedDict + sync to Pydantic v2 + async (PR #2, PR #3). The migration is complete and tests pass, but a code review reveals several categories of leftover issues: committed bytecode, mixed async frameworks, fragile error handling patterns, `global` state, and test quality gaps.

This plan is organized into **7 work items** (+ 1 discovered gap). Each can be done as a separate commit on one branch (`refactor/ce-engine-post-migration-cleanup`). Do them in order — later items may touch files changed by earlier ones.

---

## Context

### Background

The ce_engine is a LangGraph-based AI work engine that:
- Uses `langchain-anthropic` for LLM calls (not PydanticAI — a key accuracy fix in Work Item 2)
- Standardized on `anyio` for all async primitives after the Pydantic v2 migration
- Uses `anyio.TaskGroup` for concurrent I/O operations
- Relies on `tenacity` for LLM retry with exponential backoff

### Relevant Learnings

- **`async-baseexception-re-raise-pattern.md`**: Documents that `asyncio.CancelledError` must be explicitly re-raised alongside `KeyboardInterrupt`, `SystemExit`, `GeneratorExit` in `BaseException` handlers — it inherits from `BaseException`, not `Exception`. The proposed exception handler pattern in Work Item 3 is **correct** — all 4 fatal exception types are properly re-raised and non-fatal timeouts fall through to the 124 return code.

- **`python-engine-review-patterns.md`**: Documents that mutable module state should be avoided; TypedDict at module scope is an antipattern. For the LLM singleton, `functools.cache` (immutable after first call) is more aligned than a holder class (still mutable).

---

## Work Items

### Work Item 1: Fix .gitignore and remove committed bytecode

**Why:** Python `.pyc` files are committed to the repo. This is a hygiene issue — bytecode is machine-specific, clutters diffs, and should never be tracked.

**What to do:**

Add these lines to the root `.gitignore`:

```
__pycache__/
*.pyc
*.pyo
.venv/
.ruff_cache/
```

Then remove the tracked bytecode:

```bash
git rm -r --cached ce_engine/tests/__pycache__/
```

Also remove `ce_engine/src/ce_engine/__pycache__/` if tracked.

**Files changed:** `.gitignore` (edit), `ce_engine/tests/__pycache__/` (deleted from tracking)

**Commit message:** `fix: add Python patterns to .gitignore, remove committed bytecode`

---

### Work Item 2: Fill in ce_engine/README.md and fix root README accuracy

**Why:** `ce_engine/README.md` is 0 bytes. The root `README.md` stack table lists PydanticAI, but `ce_engine/` does not use PydanticAI — it uses LangGraph with `langchain-anthropic`, which is a different thing.

**What to do:**

Write a short `ce_engine/README.md` (10–15 lines) covering what the engine is, how to run it, and how to run tests. Use `pyproject.toml` as your source of truth for the dependency list.

In root `README.md`, change the stack table row from `LangGraph · PydanticAI · Anthropic SDK` to `LangGraph · langchain-anthropic` (per the actual `pyproject.toml` dependencies). Remove `httpx` from the table too — `ce_engine` does not depend on httpx directly (tenacity is used for retry, but the HTTP calls go through `langchain-anthropic`'s client).

**Files changed:** `ce_engine/README.md` (new content), `README.md` (edit stack table)

**Commit message:** `docs: fill ce_engine README, fix root README stack table accuracy`

---

### Work Item 3: Eliminate mixed async frameworks

**Why (re-scoped):** The "mixed async frameworks" characterization in the original plan was **overstated** — `asyncio` is used in only one place (`toolchain.py:47`, catching `asyncio.CancelledError`). However, the change is still valid: `anyio.get_cancelled_exc_class()` returns the backend-specific cancel exception (asyncio or trio), making the code portable regardless of which event loop backend anyio uses. This is a correctness improvement, not just cosmetic.

**Scope clarification:** There is no widespread framework mixing. The change is isolated to one exception-handling pattern in `toolchain.py`.

**What to do:**

In `src/ce_engine/toolchain.py`:
- Remove `import asyncio`
- In the `run_command` exception handler, replace `asyncio.CancelledError` with `anyio.get_cancelled_exc_class()`:

```python
except BaseException as exc:
    cancelled = anyio.get_cancelled_exc_class()
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit, cancelled)):
        raise
    return CommandResult(returncode=124, stdout="", stderr="Command timed out")
```

This pattern is **correct** — confirmed by the `async-baseexception-re-raise-pattern.md` learning: all 4 fatal types are re-raised, and non-fatal timeouts fall through to the 124 return.

In `tests/test_nodes.py`:
- Remove `import asyncio`
- Replace `await asyncio.sleep(...)` with `await anyio.sleep(...)` and add `import anyio`

**Files changed:** `src/ce_engine/toolchain.py`, `tests/test_nodes.py`

**Commit message:** `refactor: replace asyncio imports with anyio equivalents`

---

### Work Item 4: Replace global LLM singleton with `functools.cache`

**Why:** `nodes.py` uses `global _llm` to lazily create the LLM client. The `global` keyword is a Python antipattern — it makes testing harder and hides state. However, `functools.cache` is preferred over the holder pattern per the `python-engine-review-patterns.md` learning — it makes the cached value **immutable after first call**, which is more aligned with the connection-pool-preservation intent.

**What to do:**

Replace the `global` pattern with `functools.cache`:

```python
import functools

@functools.cache
def _get_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model_name=settings.model_name,
        timeout=60.0,
    )
```

**Why this is better than the holder pattern:**
- `functools.cache` makes the cached return value immutable after first call — no mutable state at all
- Simpler than a holder class — one decorator line
- Thread-safe by design (CPython guarantees)
- The original intent ("preserve connection pool across retries") is preserved identically

If `functools.cache` is too new (Python 3.9+), use `functools.lru_cache(maxsize=None)` which is equivalent.

Tests can still reset via `functools.cache` clear: `_get_llm.cache_clear()`.

**Files changed:** `src/ce_engine/nodes.py`

**Commit message:** `refactor: replace global LLM singleton with functools.cache`

---

### Work Item 5: Replace fragile string matching in route_validate

**Why (confirmed by all reviewers):** `graph.py` has `_route_validate` checking `"tests failed" in state.error_delta.lower()`. This is fragile — if the error message wording changes even slightly, the routing breaks silently. The graph would terminate instead of retrying failed tests. **This is the most architecturally significant work item.**

**What to do:**

Add a boolean field to `WorkState`:

```python
# In state.py, add to WorkState:
tests_passed: bool = True
```

In `validate_node` (nodes.py), set `tests_passed=False` when pytest fails:

```python
if pytest_result.returncode != 0:
    return {
        "error_current": final_errors,
        "error_delta": f"Tests failed ({pytest_result.returncode}). ...",
        "work_intent": make_continue_intent(),
        "tests_passed": False,
    }
# ...at the end:
return {
    "error_current": final_errors,
    "error_delta": final_delta,
    "tests_passed": True,
}
```

In `graph.py`, update the routing function:

```python
def _route_validate(state: WorkState) -> str:
    return "llm_work_node" if not state.tests_passed else "END"
```

Update `test_graph.py` tests for `TestRouteValidate` to use the new field instead of matching on `error_delta` strings.

**Files changed:** `src/ce_engine/state.py`, `src/ce_engine/nodes.py`, `src/ce_engine/graph.py`, `tests/test_graph.py`

**Commit message:** `refactor: replace string-match routing with structured tests_passed flag`

---

### Work Item 6: Make validate_node run ruff + ty concurrently

**Why:** `prefetch_node` already runs ruff and ty concurrently via `anyio.create_task_group()`, but `validate_node` runs them **sequentially** (confirmed by performance-oracle analysis of lines 302-303). `error_compact_node` already runs them concurrently — the original plan's description was outdated. Extracting a shared helper will:

1. Make `validate_node` concurrent — recovering ~43% of wall-clock time per lint pass (at ruff=1.5s, ty=2s: 3.5s sequential → 2s concurrent)
2. Eliminate ~12 lines of duplicated task-group boilerplate per node
3. Centralize the pattern for future changes (adding a third tool, adjusting timeouts, adding instrumentation)

**What to do:**

Extract a shared helper in `nodes.py`:

```python
async def _run_lint_checks(path: str = ".") -> tuple[list[RuffError], str]:
    """Run ruff and ty concurrently. Returns (ruff_errors, ty_output)."""
    ruff_errors: list[RuffError] = []
    ty_output: str = ""

    async def _ruff() -> None:
        nonlocal ruff_errors
        ruff_errors = await run_ruff_check(path)

    async def _ty() -> None:
        nonlocal ty_output
        ty_output = await run_ty_check(path)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_ruff)
        tg.start_soon(_ty)

    return ruff_errors, ty_output
```

Then use it in `prefetch_node`, `validate_node`, and `error_compact_node` to replace duplicated task group code.

**Files changed:** `src/ce_engine/nodes.py`

**Commit message:** `refactor: extract shared concurrent lint helper, DRY three nodes`

---

### Work Item 7: Fix test quality issues

**Why:** Several tests have correctness issues that could mask real bugs. Architecture-strategist review found **two additional bugs** beyond what the original plan identified.

**What to do — five sub-tasks:**

**7a.** In `tests/test_nodes.py` `TestPrefetchConcurrentRace`, the `mock_run_command` returns a raw namespace object with `bytes` attributes (`stdout=b""`) instead of a `CommandResult` with `str` attributes. Fix to return `CommandResult(returncode=0, stdout="", stderr="")`.

**7b.** In `tests/test_integration.py` and `tests/test_nodes.py`, the mock `run_command` signature uses `*, timeout` (keyword-only) but the real function in `toolchain.py` accepts `timeout` as positional-or-keyword. Make the real signature keyword-only:

```python
# In toolchain.py, change:
async def run_command(cmd: list[str], timeout: float = 30.0) -> CommandResult:
# To:
async def run_command(cmd: list[str], *, timeout: float = 30.0) -> CommandResult:
```

**7c.** In `tests/conftest.py`, replace `__import__("os")` with a normal `import os` at the top of the file.

**7d.** In `tests/test_integration.py`, after 7b makes `timeout` keyword-only, verify the integration test still passes. The call site `run_command(cmd, timeout=settings.git_timeout)` is already using `timeout` as a keyword argument, so this should be a no-op — but verify.

**7e.** (Discovered by architecture-strategist) Fix `test_nodes.py` tests `test_no_json_returns_continue` and `test_empty_output_returns_continue`. The code at `nodes.py:77-78` defaults to `"blocked"` intent when parsing fails. The tests expect `"continue"` — **these test expectations are wrong**. Change the expected intent in these tests to `"blocked"`. The code is correct; the tests have wrong expectations.

**Files changed:** `src/ce_engine/toolchain.py` (signature), `tests/conftest.py`, `tests/test_nodes.py`, `tests/test_integration.py`

**Commit message:** `fix: correct mock signatures, return types, and imports in tests`

---

### Work Item 8 (discovered): Fix prefetch_node return type annotation

**Why:** `nodes.py` line 81 returns `async def prefetch_node(state: WorkState) -> dict`. `dict` is too vague — should be `dict[str, Any]` per the python-engine-review-patterns guidance.

**What to do:**

In `src/ce_engine/nodes.py`, change:
```python
async def prefetch_node(state: WorkState) -> dict:
```

To:
```python
async def prefetch_node(state: WorkState) -> dict[str, Any]:
```

Add `from typing import Any` import if not already present.

**Files changed:** `src/ce_engine/nodes.py`

**Commit message:** `fix: annotate prefetch_node return type as dict[str, Any]`

---

## What This Plan Does NOT Cover

These are things reviewed and decided to leave alone:

- **`nonlocal` in task group closures** — after extracting `_run_lint_checks` (Work Item 6), only one `nonlocal` usage remains in `prefetch_node` (for learnings). The pattern is idiomatic enough in anyio task groups and not worth over-engineering away.
- **`_call_llm` retry logic** — the RetryError unwrapping is complex but correct. Simplifying it would risk swallowing real exceptions. Leave it.
- **CLI argument parsing** — `sys.argv` is fine for a 3-arg CLI. Adding argparse for no real benefit is YAGNI.
- **WorkIntent discriminated union** — making each intent variant its own subclass would be more type-safe, but it's a breaking change to the LLM output contract and the current flat model works.
- **Replacing `unittest.mock.patch` in integration tests** — the 10+ patch calls are ugly but functional. Refactoring to dependency injection would be a larger architectural change.

## Acceptance Criteria

After all 7 items:

- [ ] `git status` shows no `__pycache__` files tracked
- [ ] `grep -r "import asyncio" ce_engine/src/ ce_engine/tests/` returns nothing
- [ ] `grep -n "global " ce_engine/src/` returns nothing
- [ ] `uv run ruff check src/ tests/` passes with zero errors
- [ ] `uv run ty check src/` passes with zero errors
- [ ] `uv run pytest -v` — all tests pass
- [ ] `_route_validate` does not contain any string matching
- [ ] `prefetch_node` return type is `dict[str, Any]` not bare `dict`

## Branch and Commit Strategy

Single branch: `refactor/ce-engine-post-migration-cleanup`

Seven commits (Items 1–7), plus Work Item 8 as a fixup commit at the end. Each commit should pass `uv run pytest` independently.

## Sources

- **Origin document:** This plan was provided as a detailed feature description for transformation into a plan document.
- Canonical async patterns: `docs/solutions/logic-errors/async-baseexception-re-raise-pattern.md`
- Code review patterns: `docs/solutions/code-quality/python-engine-review-patterns.md`
- kieran-python-reviewer: Items 5 and 7 (test fixes) are the highest-value changes; Items 3, 4, 6 have philosophical objections but are still valid improvements.
- architecture-strategist: Item 5 is the most architecturally significant (leaky abstraction via string parsing). Item 7 exposes that two tests have incorrect expectations.
- performance-oracle: validate_node runs sequentially — the `_run_lint_checks` extraction will recover ~43% wall-clock time per lint pass.
- code-simplicity-reviewer: Work Item 3's scope is narrower than stated; the anyio/asyncio mixing is isolated to one exception type.
- pattern-recognition-specialist: Confirms all anti-patterns. Holder pattern is appropriate but functools.cache is cleaner.
