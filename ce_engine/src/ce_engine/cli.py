import logging
import sys
import uuid
from pathlib import Path
from langgraph.types import Command, RunnableConfig

from ce_engine.graph import build_work_graph
from ce_engine.state import WorkState

_MAX_TASK_LENGTH = 1000


def _validate_plan_ref(plan_ref: str) -> Path:
    """Validate plan_ref is a safe local path within cwd.

    Args:
        plan_ref: The path to validate.

    Returns:
        The resolved Path if valid.

    Raises:
        SystemExit: If the path is invalid (contains .., resolves outside cwd, etc.)
    """
    # Reject paths containing .. components (path traversal attempt)
    if ".." in Path(plan_ref).parts:
        print(f"ERROR: plan_ref must not contain '..' path traversal components: {plan_ref}")
        sys.exit(1)

    resolved = Path(plan_ref).resolve()

    # Ensure the resolved path is within the current working directory
    try:
        resolved.relative_to(Path.cwd())
    except ValueError:
        print(f"ERROR: plan_ref must resolve to a path within the current working directory: {plan_ref}")
        print(f"Resolved path: {resolved}")
        sys.exit(1)

    return resolved


def _validate_task_description(task: str) -> str:
    """Validate task_description length is within bounds.

    Args:
        task: The task description to validate.

    Returns:
        The task description if valid.

    Raises:
        SystemExit: If the task description exceeds max length.
    """
    if len(task) > _MAX_TASK_LENGTH:
        print(f"ERROR: task_description exceeds maximum length of {_MAX_TASK_LENGTH} characters: {len(task)} given")
        sys.exit(1)
    return task


def _print_usage() -> None:
    print("Usage: ce-work <task_description> <plan_ref> [session_id]")
    print()
    print("Examples:")
    print("  ce-work 'Add JWT auth' .context/compound-engineering/plan/plan.md")
    print("  ce-work 'Add JWT auth' .context/compound-engineering/plan/plan.md abc-123")


def _handle_interrupt(interrupt_data: dict) -> str:
    """Present interrupt information and collect human response."""
    interrupt_type = interrupt_data.get("type", "unknown")

    if interrupt_type == "blocked":
        print("\n--- BLOCKED ---")
        print(f"Reason: {interrupt_data.get('reason', 'No reason given')}")
        options = interrupt_data.get("options", [])
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt}")
        print("Enter your choice (number or free text): ", end="", flush=True)
        raw = input().strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        return raw

    if interrupt_type == "risky_operation":
        print("\n--- APPROVAL REQUIRED ---")
        print(f"Operation: {interrupt_data.get('operation', 'unknown')}")
        print(f"Files affected: {interrupt_data.get('files', [])}")
        print("Approve? (yes/no): ", end="", flush=True)
        return input().strip().lower()

    if interrupt_type == "plan_gap":
        print("\n--- PLAN GAP DETECTED ---")
        print(f"Gap: {interrupt_data.get('description', 'No description')}")
        print("  1. Include in this work")
        print("  2. Defer to next plan")
        print("Enter choice (1/2): ", end="", flush=True)
        raw = input().strip()
        return "include in this work" if raw == "1" else "defer to next plan"

    # Unknown interrupt type — ask for free text
    print(f"\n--- PAUSED ({interrupt_type}) ---")
    print(f"Data: {interrupt_data}")
    print("Enter response: ", end="", flush=True)
    return input().strip()


def run_work(task: str, plan_ref: str, session_id: str | None = None) -> None:
    """Run or resume the work loop.

    Args:
        task: Description of the task to implement.
        plan_ref: Path to the plan file.
        session_id: Existing session ID to resume. If None, starts fresh.
    """
    graph = build_work_graph()
    thread_id = session_id or str(uuid.uuid4())
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    print(f"Session ID: {thread_id}")
    print("(Pass this ID as the third argument to resume this session)\n")

    if session_id:
        # Resume an existing interrupted session
        result = graph.invoke(Command(resume=True), config)
    else:
        # Start a new session
        initial_state: WorkState = {
            "task_description": task,
            "plan_ref": plan_ref,
            "iteration": 0,
            "max_iterations": 5,
            "tool_call_budget": 10,
            "error_baseline": [],
            "error_current": [],
            "error_delta": "",
            "context_pack_path": ".context/compound-engineering/context-pack.md",
            "relevant_learnings": "",
            "work_intent": None,
            "llm_response": "",
            "approved": False,
            "session_id": thread_id,
        }
        result = graph.invoke(initial_state, config)

    # Handle any interrupts by looping until the graph completes
    while True:
        interrupts = result.get("__interrupt__")
        if not interrupts:
            # No interrupt — graph has completed
            break
        interrupt_data = interrupts[0].value if hasattr(interrupts[0], "value") else interrupts[0]
        if not isinstance(interrupt_data, dict):
            logging.warning("Unexpected interrupt value type: %s", type(interrupt_data))
            interrupt_data = {"type": "unknown", "data": str(interrupt_data)[:200]}
        response = _handle_interrupt(interrupt_data)
        result = graph.invoke(Command(resume=response), config)

    print("\n--- WORK LOOP COMPLETE ---")
    print(f"Final error state: {result.get('error_delta', 'unknown')}")
    print(f"Session ID: {thread_id}")


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 3:
        _print_usage()
        sys.exit(0)

    task = _validate_task_description(sys.argv[1])
    plan_ref = str(_validate_plan_ref(sys.argv[2]))
    session_id = sys.argv[3] if len(sys.argv) > 3 else None

    run_work(task, plan_ref, session_id)


if __name__ == "__main__":
    main()
