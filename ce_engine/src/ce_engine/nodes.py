import json
import subprocess
from pathlib import Path
from typing import cast

from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from langchain_anthropic import ChatAnthropic
from langgraph.types import interrupt

from ce_engine.prompts import build_work_prompt
from ce_engine.state import WorkIntent, WorkState


def _run_command(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """Run a command with a timeout, returning (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.returncode, result.stdout, result.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", "Command timed out")


def _make_empty_intent() -> WorkIntent:
    return WorkIntent(
        intent="continue",
        reason=None,
        options=None,
        operation=None,
        files=None,
        description=None,
    )


def prefetch_node(state: WorkState) -> WorkState:
    """Run all tools and build the Context Pack before any LLM call."""
    ruff_returncode, ruff_stdout, ruff_stderr = _run_command(
        ["ruff", "check", "--output-format=json", "."],
        timeout=30,
    )
    try:
        ruff_errors = (
            json.loads(ruff_stdout) if ruff_stdout.strip() else []
        )
    except json.JSONDecodeError:
        ruff_errors = []

    ty_returncode, ty_stdout, ty_stderr = _run_command(
        ["ty", "check", "."],
        timeout=30,
    )
    ty_errors = ty_stdout.strip()

    error_count = len(ruff_errors)
    error_delta = (
        f"{error_count} ruff errors detected.\n{ty_errors}"
        if error_count > 0 or ty_errors
        else "No errors found."
    )

    # Read the two most recent files in .context/compound-engineering/learnings/
    learnings_dir = Path(".context/compound-engineering/learnings")
    if learnings_dir.exists():
        recent = sorted(learnings_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:2]
        relevant_learnings = "\n".join(p.read_text()[:500] for p in recent) if recent else ""
    else:
        relevant_learnings = ""

    # Get current git branch
    _, git_branch_stdout, _ = _run_command(["git", "branch", "--show-current"], timeout=30)
    git_branch = git_branch_stdout.strip() or "unknown"

    # Get list of changed files
    _, git_diff_stdout, _ = _run_command(["git", "diff", "--name-only", "HEAD"], timeout=30)
    git_diff = git_diff_stdout.strip() or "none"

    context_pack_path = ".context/compound-engineering/context-pack.md"
    Path(context_pack_path).parent.mkdir(parents=True, exist_ok=True)

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
        f"  task: {state['task_description']}\n"
        f"  plan_ref: {state['plan_ref']}\n"
        "</current_task>\n\n"
        "<pre_fetched>\n"
        "  ruff_errors: |\n"
        f"    {json.dumps(ruff_errors, indent=4)}\n"
        "  ty_errors: |\n"
        f"    {ty_errors}\n"
        "</pre_fetched>\n\n"
        "<relevant_learnings>\n"
        f"  {relevant_learnings or 'None available.'}\n"
        "</relevant_learnings>\n"
    )
    Path(context_pack_path).write_text(context_pack_content)

    return cast(WorkState, {
        **state,
        "error_baseline": ruff_errors,
        "error_current": ruff_errors,
        "error_delta": error_delta,
        "context_pack_path": context_pack_path,
        "relevant_learnings": relevant_learnings,
    })


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _call_llm(prompt: str) -> str:
    """Call the LLM with exponential backoff retry (max 3 attempts)."""
    model = ChatAnthropic(model_name="claude-sonnet-4-20250514")
    response = model.invoke(prompt)
    return str(response.content)


def llm_work_node(state: WorkState) -> WorkState:
    """Call the LLM to perform one iteration of work."""
    prompt = build_work_prompt(state)
    try:
        response_text = _call_llm(prompt)
    except RetryError as e:
        # Persistent failure after retries — return a structured blocked intent
        error_reason = f"LLM call failed after 3 attempts: {e}"
        return cast(WorkState, {
            **state,
            "llm_response": None,
            "work_intent": {
                "intent": "blocked",
                "reason": error_reason,
                "options": None,
                "operation": None,
                "files": None,
                "description": None,
            },
            "iteration": state["iteration"] + 1,
        })

    # The LLM is instructed to put a JSON intent on the final line.
    lines = response_text.strip().split("\n")
    last_line = lines[-1].strip()
    try:
        intent_data = json.loads(last_line)
    except json.JSONDecodeError:
        intent_data = {"intent": "continue"}

    work_intent: WorkIntent = {
        "intent": cast(Literal["continue", "done", "blocked", "risky_operation", "plan_gap"], intent_data.get("intent", "continue")),
        "reason": cast(str | None, intent_data.get("reason")),
        "options": cast(list[str] | None, intent_data.get("options")),
        "operation": cast(str | None, intent_data.get("operation")),
        "files": cast(list[str] | None, intent_data.get("files")),
        "description": cast(str | None, intent_data.get("description")),
    }

    return cast(WorkState, {
        **state,
        "llm_response": response_text,
        "work_intent": work_intent,
        "iteration": state["iteration"] + 1,
    })


def error_compact_node(state: WorkState) -> WorkState:
    """Re-run ruff, compute the delta from baseline, and update state."""
    ruff_returncode, ruff_stdout, ruff_stderr = _run_command(
        ["ruff", "check", "--output-format=json", "."],
        timeout=30,
    )
    try:
        current_errors = (
            json.loads(ruff_stdout) if ruff_stdout.strip() else []
        )
    except json.JSONDecodeError:
        current_errors = []

    baseline_count = len(state["error_baseline"])
    current_count = len(current_errors)
    resolved = baseline_count - current_count

    if resolved >= 0:
        delta = (
            f"{resolved} of {baseline_count} ruff errors resolved. "
            f"{current_count} remaining."
        )
    else:
        delta = (
            f"{abs(resolved)} new ruff errors introduced. "
            f"{current_count} total."
        )

    return cast(WorkState, {**state, "error_current": current_errors, "error_delta": delta})


def human_interrupt_node(state: WorkState) -> WorkState:
    """Pause and ask the human to resolve a blocking question."""
    intent = state["work_intent"] or _make_empty_intent()
    response = interrupt(value={
        "type": "blocked",
        "reason": intent["reason"],
        "options": intent.get("options") or [],
        "iteration": state["iteration"],
    })
    # Append the human's decision to the Context Pack so the next
    # iteration starts with it as context.
    pack_path = Path(state["context_pack_path"])
    existing = pack_path.read_text()
    pack_path.write_text(
        existing + f"\n<human_decision>\n  {response}\n</human_decision>\n"
    )
    return cast(WorkState, {**state, "work_intent": _make_empty_intent()})


def risky_op_interrupt_node(state: WorkState) -> WorkState:
    """Pause and ask the human to approve a potentially destructive operation."""
    intent = state["work_intent"] or _make_empty_intent()
    response = interrupt(value={
        "type": "risky_operation",
        "operation": intent["operation"],
        "files": intent.get("files") or [],
        "message": "Approve this operation before it runs?",
        "options": ["approve", "reject"],
    })
    approved = str(response).lower() in ("approve", "yes", "y", "true")
    return cast(WorkState, {**state, "approved": approved})


def validate_node(state: WorkState) -> WorkState:
    """Run final toolchain checks after the LLM declares the work done."""
    ruff_returncode, ruff_stdout, ruff_stderr = _run_command(
        ["ruff", "check", "--output-format=json", "."],
        timeout=30,
    )
    try:
        final_errors = (
            json.loads(ruff_stdout) if ruff_stdout.strip() else []
        )
    except json.JSONDecodeError:
        final_errors = []

    ty_returncode, ty_stdout, ty_stderr = _run_command(
        ["ty", "check", "."],
        timeout=30,
    )
    ty_status = "clean" if not ty_returncode else ty_stdout.strip()

    pytest_returncode, pytest_stdout, pytest_stderr = _run_command(
        ["uv", "run", "pytest", "--tb=short", "-q"],
        timeout=120,
    )
    if pytest_returncode != 0:
        # Tests failed — signal the work loop to continue fixing
        return cast(WorkState, {
            **state,
            "error_current": final_errors,
            "error_delta": (
                f"Tests failed. Fix failing tests before continuing.\n"
                f"pytest output:\n{pytest_stdout}\n{pytest_stderr}"
            ),
            "work_intent": _make_empty_intent(),
            "task_description": "Fix failing tests",
        })

    final_delta = (
        f"Final: {len(final_errors)} ruff errors. ty: {ty_status}"
    )

    return cast(WorkState, {**state, "error_current": final_errors, "error_delta": final_delta})


def plan_gap_node(state: WorkState) -> WorkState:
    """Record a plan gap and ask the human whether to include it or defer."""
    intent = state["work_intent"] or _make_empty_intent()
    gap_path = Path(".context/compound-engineering/plan-gaps.md")
    gap_path.parent.mkdir(parents=True, exist_ok=True)
    existing = gap_path.read_text() if gap_path.exists() else ""
    gap_path.write_text(
        existing
        + f"\n## Gap found in iteration {state['iteration']}\n"
        + f"{intent['description']}\n"
    )
    response = interrupt(value={
        "type": "plan_gap",
        "description": intent["description"],
        "options": ["include in this work", "defer to next plan"],
    })
    if str(response).lower().startswith("include"):
        return cast(WorkState, {**state, "work_intent": _make_empty_intent()})
    # User deferred — treat as done
    return cast(WorkState, {
        **state,
        "work_intent": {
            "intent": "done",
            "reason": None,
            "options": None,
            "operation": None,
            "files": None,
            "description": None,
        },
    })
