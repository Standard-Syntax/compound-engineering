---
title: Python LangGraph engine code review patterns
category: code-quality
date: 2026-03-24
tags: [python, langgraph, ce-engine, code-review, tenacity, subprocess, typeddict]
---

## Problem

A multi-agent code review of the `ce_engine` LangGraph work engine surfaced 9 findings (5 P1, 3 P2, 1 P3). The issues fell into recurring pattern categories: subprocess reliability, LLM reliability, type safety, CLI input validation, and agent-native parity.

## Root Cause

Each issue stemmed from a predictable class of mistake:

- **Subprocess hangs**: No `timeout` on external tool calls
- **LLM fragility**: No retry or error handling around model calls
- **Mutable module state**: TypedDict used as a mutable constant
- **CLI trust**: User-provided arguments used without path validation
- **Skill/command drift**: Slash commands and skill files describing divergent behaviors
- **Dead code**: Unused exports, imports, and helper functions

## Solution

### 1. Subprocess timeout helper

Never call `subprocess.run` without a timeout. Extract a helper:

```python
def _run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", "Command timed out")
```

Use `timeout=30` for linters/type-checkers, `timeout=120` for test runners.

### 2. LLM retry with tenacity

Wrap LLM calls with `@retry` from `tenacity` and handle persistent failures gracefully:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True)
def _call_llm(prompt: str) -> str:
    return model.invoke(prompt)

# In the node:
try:
    response = _call_llm(prompt)
except RetryError:
    return cast(WorkState, {**state, "work_intent": {"intent": "blocked", "reason": "LLM call failed after 3 retries", ...}})
```

### 3. TypedDict as factory, not constant

Never define a mutable TypedDict at module scope:

```python
# Wrong — mutable shared state
_EMPTY_INTENT: WorkIntent = {"intent": "continue", "reason": None, ...}

# Right — factory returns a fresh dict each call
def _make_empty_intent() -> WorkIntent:
    return WorkIntent(intent="continue", reason=None, options=None, operation=None, files=None, description=None)
```

### 4. CLI argument validation

Validate before use. Reject path traversal and bound input length:

```python
def _validate_plan_ref(plan_ref: str) -> Path:
    if ".." in plan_ref:
        sys.exit("Error: plan_ref must not contain '..'")
    resolved = Path(plan_ref).resolve()
    resolved.relative_to(Path.cwd())  # raises if outside cwd
    return resolved

def _validate_task_description(task: str) -> str:
    if len(task) > 1000:
        sys.exit("Error: task description must be <= 1000 characters")
    return task
```

### 5. Interrupt value type checking

After extracting an interrupt value, validate its type before accessing it as a dict:

```python
interrupt_data = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
if not isinstance(interrupt_data, dict):
    logging.warning("Unexpected interrupt value type: %s", type(interrupt_data))
    interrupt_data = {"type": "unknown", "data": str(interrupt_data)[:200]}
```

### 6. Agent-native command parity

Every slash command must have a corresponding agent-accessible skill. When creating a new command, create `plugins/compound-engineering/skills/<name>/SKILL.md` in parallel. Ensure skill and command describe the same execution approach — divergence creates confusion when an agent loads the skill vs. a user invoking the command.

### 7. Model names: full versioned strings

Always use the full versioned model string per CLAUDE.md convention:

```python
# Wrong
ChatAnthropic(model_name="claude-sonnet-4-6")

# Right
ChatAnthropic(model_name="claude-sonnet-4-20250514")
```

## Prevention

- **Subprocess calls**: Add timeout every time, no exceptions
- **External API calls**: Wrap with tenacity retry; handle persistent failures with structured error states
- **CLI args**: Always validate paths and bound lengths before using in file operations or prompts
- **TypedDict at module scope**: Use factory functions, never mutable module-level dicts
- **Slash commands**: Create skill counterpart at the same time as the command
- **Skills vs. commands**: Review for divergence at merge time; update skill when command behavior changes

## Related

- `docs/solutions/code-quality/python-engine-review-patterns.md` (this file)
- `docs/solutions/skill-design/beta-skills-framework.md` — beta skill rollout pattern
- `docs/solutions/skill-design/claude-permissions-optimizer-classification-fix.md` — normalization ordering
