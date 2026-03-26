---
title: "Code Review PR #3 — P1/P2 Bug Fixes: ce_engine Phase 2"
category: logic-errors
date: 2026-03-25
tags:
  - code-review
  - bugfix
  - p1
  - p2
  - async
  - tenacity
  - race-condition
  - pytest
  - error-handling
  - anyio
related_issues:
  - "PR #3"
summary: "Code review of PR #3 identified and fixed 8 P1/P2 bugs in ce_engine including vacuous test assertions, asyncio.CancelledError handling, TOCTOU race in CLI, swallowed exceptions via tenacity RetryError, unbounded error output, missing test mocks, sequential vs concurrent execution, and fragile routing logic."
---

## Problem

Code review of PR #3 (refactor: ce_engine phase 2) identified 8 P1/P2 bugs in the ce_engine async coding agent. Multiple issues with async exception handling, race conditions, incomplete test mocks, and sequential vs concurrent I/O were found and fixed.

## Root Causes

### 1. `asyncio.CancelledError` Silently Swallowed

`run_command()` in `toolchain.py` caught `BaseException` but only re-raised `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`. `asyncio.CancelledError` (raised when `anyio.fail_after` triggers) inherits from `BaseException`, not `Exception`, so it was converted to a fake timeout result.

```python
# Vulnerable: asyncio.CancelledError fell through to the timeout return
except BaseException as exc:
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise  # Missing: asyncio.CancelledError
    return CommandResult(returncode=124, stdout="", stderr="Command timed out")
```

### 2. TOCTOU Race in CLI Response File

`_get_interrupt_response()` checked `exists()` then called `read_text()` then `unlink()` — three separate operations with race windows between each.

### 3. `_call_llm` Swallowing Fatal Exceptions via tenacity

`AsyncRetrying` wraps any exception raised inside `with attempt:` in a `RetryError`. The outer `except RetryError` caught `KeyboardInterrupt` and re-raised it as `RuntimeError`, making the process unkillable during LLM calls.

### 4. Unbounded pytest Output in State

`validate_node` embedded full `pytest stdout/stderr` in `error_delta`. For large test suites this could be megabytes.

### 5. Incomplete Mock in Integration Test

`test_integration.py` did not mock `run_pytest` — causing the test to hang waiting for the real subprocess. Also missing several `settings` attributes on the mock.

### 6. Sequential `error_compact_node` I/O

`error_compact_node` ran `run_ruff_check` and `run_ty_check` sequentially (~4s total) while `prefetch_node` proved the concurrent `anyio.TaskGroup` pattern works.

---

## Solutions

### Fix 1: Add `asyncio.CancelledError` to Re-raised Exceptions

```python
# toolchain.py
except BaseException as exc:
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit, asyncio.CancelledError)):
        raise
    return CommandResult(returncode=124, stdout="", stderr="Command timed out")
```

### Fix 2: Replace TOCTOU Check with Try/Except

```python
# cli.py _get_interrupt_response()
response_file = Path(f"/tmp/ce-work-{session_id}-{interrupt_type}.response")
try:
    response = response_file.read_text().strip()
except FileNotFoundError:
    return input().strip()
else:
    response_file.unlink(missing_ok=True)
    return response
```

### Fix 3: Re-raise Fatal Exceptions Before Handling RetryError

```python
# nodes.py _call_llm()
result: str | None = None
try:
    async for attempt in AsyncRetrying(...):
        with attempt:
            response = await _get_llm().ainvoke(prompt)
            result = str(response.content)
except BaseException as exc:
    if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
        raise
    if isinstance(exc, RetryError) and exc.last_attempt is not None:
        real_exc = exc.last_attempt.exception()
        if isinstance(real_exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise real_exc from exc
    if result is None:
        raise RuntimeError("AsyncRetrying loop completed without result") from exc
    raise RuntimeError(f"LLM call failed: {exc}") from exc
return result
```

### Fix 4: Truncate pytest Output

```python
# nodes.py validate_node()
stdout = pytest_result.stdout[:500]
stderr = pytest_result.stderr[:200]
suffix = "..." if len(pytest_result.stdout) > 500 or len(pytest_result.stderr) > 200 else ""
return {
    "error_delta": (
        f"Tests failed ({pytest_result.returncode}). "
        f"Fix failing tests before continuing.\n"
        f"pytest output:\n{stdout}{suffix}\n{stderr}{suffix}"
    ),
    ...
}
```

### Fix 5: Complete Mock Setup in Integration Test

```python
# test_integration.py
async def mock_pytest(path: str = ".") -> CommandResult:
    return CommandResult(returncode=0, stdout="", stderr="")

with (
    patch("ce_engine.nodes.run_ruff_check", mock_ruff_check),
    patch("ce_engine.nodes.run_ty_check", mock_ty_check),
    patch("ce_engine.nodes.run_command", mock_run_command),
    patch("ce_engine.nodes.run_pytest", mock_pytest),
    patch("ce_engine.nodes._call_llm", mock_call_llm),
    patch("ce_engine.nodes.settings") as mock_settings,
):
    mock_settings.learnings_path = learnings_dir
    mock_settings.context_pack_path = context_pack
    mock_settings.git_timeout = 5.0
    mock_settings.lint_timeout = 5.0
    mock_settings.pytest_timeout = 60.0
    mock_settings.plan_gaps_path = tmp_path / "plan-gaps.md"
    mock_settings.model_name = "test-model"
    mock_settings.max_iterations = 3
    mock_settings.tool_call_budget = 10
```

### Fix 6: Parallelize `error_compact_node`

```python
# nodes.py error_compact_node()
current_errors: list[RuffError] = []
ty_output: str = ""

async def _run_ruff() -> None:
    nonlocal current_errors
    current_errors = await run_ruff_check(".")

async def _run_ty() -> None:
    nonlocal ty_output
    ty_output = await run_ty_check(".")

async with anyio.create_task_group() as tg:
    tg.start_soon(_run_ruff)
    tg.start_soon(_run_ty)
```

---

## Prevention Strategies

1. **CancelledError handling**: Always audit `BaseException` subclasses in async exception handlers. The four fatal types are: `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, `asyncio.CancelledError`. All four must be re-raised.

2. **TOCTOU races**: Never check-then-act on filesystem state. Use `try/except/else` or `missing_ok=True` — the check itself creates the race window.

3. **tenacity wrapping**: When using tenacity retry, catch `BaseException` first (before tenacity wraps) to re-raise fatals immediately. Then unwrap `RetryError.last_attempt` to check the real exception type.

4. **Unbounded output**: Define module-level constants (`MAX_STDOUT_TRUNCATE = 500`, `MAX_STDERR_TRUNCATE = 200`) and always truncate before embedding subprocess output in graph state.

5. **Integration test mocks**: All subprocess-calling functions AND all settings attributes accessed during the test must be mocked together. Use a complete conftest fixture to avoid omissions.

6. **Concurrent I/O**: Once `anyio.TaskGroup` concurrency is proven working in one node, apply the same pattern to all other nodes running independent I/O operations.

### Code Review Checklist for ce_engine Async Code

Before merging async code, verify:

- [ ] All `async with anyio.create_task_group()` calls use closure-captured variables, not shared collections with assumed ordering
- [ ] No mixing of `asyncio.to_thread` and `anyio.to_thread.run_sync` in the same file
- [ ] Exception handlers that catch `BaseException` explicitly re-raise `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, and `asyncio.CancelledError`
- [ ] All `match/case` statements on state fields cover all possible values with explicit cases (no bare `_` as primary routing)
- [ ] File reads are guarded with `.exists()` or wrapped in `try/except FileNotFoundError`
- [ ] State update dicts do not accidentally overwrite fields that should be preserved
- [ ] New intent types require updates to ALL routing functions (`_route_intent`, `_route_validate`, `_route_after_*`)
- [ ] Dead code paths raise `AssertionError` or are impossible to reach

### Test Case Suggestions

Add these tests to prevent regressions:

```python
# Test that asyncio.CancelledError propagates through run_command
@pytest.mark.asyncio
async def test_run_command_cancellation():
    async def raise_cancelled():
        await asyncio.sleep(0.01)
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await run_command("sleep 10", timeout=60.0, callee=raise_cancelled)

# Test _call_llm propagates KeyboardInterrupt
@pytest.mark.asyncio
async def test_call_llm_fatal_exception_propagates():
    async def raise_interrupt():
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        await _call_llm("test", _get_llm=raise_interrupt)

# Test risky_operation routes to correct node
@pytest.mark.asyncio
async def test_risky_operation_routes_to_interrupt():
    state = WorkState(work_intent=WorkIntent(intent="risky_operation"))
    assert _route_intent(state) == "risky_op_interrupt_node"

# Test validate_node does not overwrite task_description
@pytest.mark.asyncio
async def test_validate_node_preserves_task_description():
    state = WorkState(task_description="original task")
    result = await validate_node(state)
    assert result.get("task_description") == "original task"
```

### Best Practices for ce_engine Async Code

1. **Structured Concurrency First**: Prefer `anyio.TaskGroup` for concurrent async operations. It guarantees all tasks complete before the block exits.

2. **Avoid Shared Mutable State in TaskGroups**: Use closure-captured variables with `nonlocal` declarations. Never use indexed access to shared collections.

3. **Name Your Async Operations**: Use named functions (`async def _run_ruff()`) rather than inline lambdas in `start_soon()` calls for better stack traces.

4. **Timeout with `fail_after` Only**: `anyio.run_process()` has no built-in timeout. Always wrap in `anyio.fail_after()`.

5. **Test Concurrent Code with Randomization**: Add jitter/delay to async mocks to catch ordering assumptions. Run tests multiple times.

6. **Use Frozen Models for Immutable Data**: Mark data classes and Pydantic models as frozen when they represent facts that should not change (like `RuffError`).

7. **Document Why BaseException**: If you must catch `BaseException`, add a comment explaining why and what exceptions are re-raised.

8. **Keep Router Functions Pure**: Routing functions should be pure transformations of state with no side effects. This makes them testable and predictable.

---

## Related Documentation

- `docs/solutions/code-quality/python-engine-review-patterns.md` — Prior ce_engine review patterns (tenacity retry, subprocess timeouts). Consider linking from that doc to this one for the async/tenacity findings.
- `docs/plans/2026-03-25-002-refactor-ce-engine-phase2-bugs-async-plan.md` — Phase 2 plan (source of truth for this work)

**Cross-references added by this update:**
- `code-quality/python-engine-review-patterns.md` → `logic-errors/async-baseexception-re-raise-pattern.md` (missing link now documented)

## Changes

| File | Change |
|------|--------|
| `ce_engine/src/ce_engine/toolchain.py` | Added `asyncio.CancelledError` to re-raise tuple |
| `ce_engine/src/ce_engine/cli.py` | Replaced TOCTOU pattern with try/except/else |
| `ce_engine/src/ce_engine/nodes.py` | Fixed `_call_llm` fatal exception handling, parallelized `error_compact_node`, truncated pytest output |
| `ce_engine/tests/test_nodes.py` | Removed vacuous `ty_output` assertion |
| `ce_engine/tests/test_integration.py` | Added `mock_pytest`, complete settings mock, all required patches |
