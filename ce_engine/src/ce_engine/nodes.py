"""LangGraph nodes for the CE work engine.

All nodes are async def. Subprocess calls use anyio.fail_after() for timeout
(anyio.run_process has NO built-in timeout parameter). A singleton LLM client
is created at module level to preserve connection pool across retries.
"""

import json
from pathlib import Path

import anyio
from anyio.to_thread import run_sync as to_thread_run_sync
from httpx import HTTPError as HttpxHTTPError
from langchain_anthropic import ChatAnthropic
from langgraph.types import interrupt
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ce_engine.config import settings
from ce_engine.prompts import build_work_prompt
from ce_engine.state import RuffError, WorkIntent, WorkState, make_continue_intent
from ce_engine.toolchain import (
    compute_error_delta,
    run_command,
    run_pytest,
    run_ruff_check,
    run_ty_check,
)

# Lazy LLM singleton -- created once on first call to preserve connection pool
_llm: ChatAnthropic | None = None


def _get_llm() -> ChatAnthropic:
    """Lazily initialize the LLM client."""
    global _llm
    if _llm is None:
        _llm = ChatAnthropic(
            model_name=settings.model_name,
            timeout=60.0,  # read timeout; connect uses httpx default
        )
    return _llm


def _parse_intent(response_text: str) -> WorkIntent:
    """Parse intent from LLM response by scanning backwards for JSON.

    The LLM is instructed to put a JSON intent on the final line, but it
    may include explanatory text above it. This scans backwards from the
    last line until a valid JSON object containing 'intent' is found.
    """
    lines = response_text.strip().split("\n")
    for i in range(len(lines) - 1, -1, -1):
        candidate = lines[i].strip()
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "intent" in data:
                return WorkIntent(
                    intent=data.get("intent", "continue"),
                    reason=data.get("reason"),
                    options=data.get("options"),
                    operation=data.get("operation"),
                    files=data.get("files"),
                    description=data.get("description"),
                )
        except json.JSONDecodeError:
            continue
    # No valid JSON found -- default to continue
    return make_continue_intent()


async def prefetch_node(state: WorkState) -> dict:
    """Run all tools and build the Context Pack before any LLM call.

    Runs ruff and ty concurrently via anyio.TaskGroup for 30-50% time reduction.
    """
    # Run ruff and ty checks concurrently
    ruff_errors: list[RuffError] = []
    ty_output: str = ""

    async def _run_ruff() -> None:
        nonlocal ruff_errors
        ruff_errors = await run_ruff_check(".")

    async def _run_ty() -> None:
        nonlocal ty_output
        ty_output = await run_ty_check(".")

    async with anyio.create_task_group() as tg:
        tg.start_soon(_run_ruff)
        tg.start_soon(_run_ty)

    error_count = len(ruff_errors)
    ty_status = ty_output if ty_output else "clean"
    error_delta = (
        f"{error_count} ruff errors detected.\nty: {ty_status}"
        if error_count > 0 or ty_output
        else "No errors found."
    )

    # Read the two most recent files in learnings/ (non-blocking)
    def _read_learnings() -> str:
        learnings_dir = settings.learnings_path
        if not learnings_dir.exists():
            return ""
        recent = sorted(
            learnings_dir.glob("*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:2]
        return "\n".join(p.read_text()[:500] for p in recent) if recent else ""

    relevant_learnings = await to_thread_run_sync(_read_learnings)

    # Get current git branch
    git_result = await run_command(
        ["git", "branch", "--show-current"], timeout=settings.git_timeout
    )
    git_branch = git_result.stdout.strip() or "unknown"

    # Get list of changed files
    diff_result = await run_command(
        ["git", "diff", "--name-only", "HEAD"], timeout=settings.git_timeout
    )
    git_diff = diff_result.stdout.strip() or "none"

    context_pack_path = settings.context_pack_path
    context_pack_path.parent.mkdir(parents=True, exist_ok=True)

    context_pack_content = (
        "<project>\n"
        "  python: 3.13\n"
        "  package_manager: uv\n"
        "  linter: ruff\n"
        "  type_checker: ty\n"
        "</project>\n\n"
        "<current_task>\n"
        f"  branch: {git_branch}\n"
        f"  changed_files: {git_diff}\n"
        f"  task: {state.task_description}\n"
        f"  plan_ref: {state.plan_ref}\n"
        "</current_task>\n\n"
        "<pre_fetched>\n"
        "  ruff_errors: |\n"
        f"    {json.dumps([e.model_dump() for e in ruff_errors], indent=4)}\n"
        "  ty_errors: |\n"
        f"    {ty_output}\n"
        "</pre_fetched>\n\n"
        "<relevant_learnings>\n"
        f"  {relevant_learnings or 'None available.'}\n"
        "</relevant_learnings>\n"
    )

    def _write_context_pack() -> None:
        context_pack_path.write_text(context_pack_content)

    await to_thread_run_sync(_write_context_pack)

    return {
        "error_baseline": ruff_errors,
        "error_current": ruff_errors,
        "error_delta": error_delta,
        "context_pack_path": context_pack_path,
        "relevant_learnings": relevant_learnings,
        "approved": False,
    }


async def _call_llm(prompt: str) -> str:
    """Call the LLM with exponential backoff retry (max 3 attempts)."""
    result: str | None = None
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type((OSError, HttpxHTTPError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    ):
        with attempt:
            response = await _get_llm().ainvoke(prompt)
            result = str(response.content)
    # AsyncRetrying with stop_after_attempt always yields at least once.
    # If we reach here without result, raise to avoid returning None.
    if result is None:
        msg = "AsyncRetrying loop completed without result"
        raise RuntimeError(msg)
    return result


async def llm_work_node(state: WorkState) -> dict:
    """Call the LLM to perform one iteration of work."""
    prompt = build_work_prompt(state)
    try:
        response_text = await _call_llm(prompt)
    except RetryError as e:
        # Persistent failure after retries -- unwrap to show the underlying exception
        last_exc = e.last_attempt.exception() if e.last_attempt else e
        error_reason = f"LLM call failed after 3 attempts: {type(last_exc).__name__}: {last_exc}"
        return {
            "llm_response": None,
            "work_intent": WorkIntent(
                intent="blocked",
                reason=error_reason,
            ),
            "iteration": state.iteration + 1,
        }

    intent = _parse_intent(response_text)

    return {
        "llm_response": response_text,
        "work_intent": intent,
        "iteration": state.iteration + 1,
    }


async def error_compact_node(state: WorkState) -> dict:
    """Re-run ruff, compute the delta from baseline, and update state."""
    current_errors = await run_ruff_check(".")
    ty_output = await run_ty_check(".")
    delta = compute_error_delta(state.error_baseline, current_errors)
    ty_status = ty_output if ty_output else "clean"
    return {
        "error_current": current_errors,
        "error_delta": f"{delta}\nty: {ty_status}",
    }


async def human_interrupt_node(state: WorkState) -> dict:
    """Pause and ask the human to resolve a blocking question."""
    intent = state.work_intent or make_continue_intent()
    response = interrupt(
        value={
            "type": "blocked",
            "reason": intent.reason,
            "options": intent.options or [],
            "iteration": state.iteration,
        }
    )
    # Append the human's decision to the Context Pack (non-blocking)
    pack_path = Path(state.context_pack_path)

    def _append_decision() -> None:
        existing = pack_path.read_text() if pack_path.exists() else ""
        pack_path.write_text(existing + f"\n<human_decision>\n  {response}\n</human_decision>\n")

    await to_thread_run_sync(_append_decision)
    return {"work_intent": make_continue_intent()}


async def risky_op_interrupt_node(state: WorkState) -> dict:
    """Pause and ask the human to approve a potentially destructive operation."""
    intent = state.work_intent or make_continue_intent()
    response = interrupt(
        value={
            "type": "risky_operation",
            "operation": intent.operation,
            "files": intent.files or [],
            "message": "Approve this operation before it runs?",
            "options": ["approve", "reject"],
        }
    )
    approved = str(response).lower() in ("approve", "yes", "y", "true")
    return {"approved": approved}


async def validate_node(state: WorkState) -> dict:
    """Run final toolchain checks after the LLM declares the work done."""
    final_errors = await run_ruff_check(".")
    ty_output = await run_ty_check(".")
    ty_status = ty_output if ty_output else "clean"

    pytest_result = await run_pytest(".")
    if pytest_result.returncode != 0:
        # Tests failed -- signal the work loop to continue fixing
        return {
            "error_current": final_errors,
            "error_delta": (
                f"Tests failed. Fix failing tests before continuing.\n"
                f"pytest output:\n{pytest_result.stdout}\n{pytest_result.stderr}"
            ),
            "work_intent": make_continue_intent(),
        }

    final_delta = f"Final: {len(final_errors)} ruff errors. ty: {ty_status}"
    return {
        "error_current": final_errors,
        "error_delta": final_delta,
    }


async def plan_gap_node(state: WorkState) -> dict:
    """Record a plan gap and ask the human whether to include it or defer."""
    intent = state.work_intent or make_continue_intent()
    gap_path = settings.plan_gaps_path
    gap_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_gap() -> None:
        existing = gap_path.read_text() if gap_path.exists() else ""
        gap_path.write_text(
            existing
            + f"\n## Gap found in iteration {state.iteration}\n"
            + f"{intent.description}\n"
        )

    await to_thread_run_sync(_write_gap)

    response = interrupt(
        value={
            "type": "plan_gap",
            "description": intent.description,
            "options": ["include in this work", "defer to next plan"],
        }
    )
    if str(response).lower().startswith("include"):
        return {"work_intent": make_continue_intent()}
    # User deferred -- treat as done
    return {
        "work_intent": WorkIntent(intent="done"),
    }
