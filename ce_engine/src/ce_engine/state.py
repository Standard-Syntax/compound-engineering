from typing import Literal, TypedDict


class WorkIntent(TypedDict):
    intent: Literal["continue", "done", "blocked", "risky_operation", "plan_gap"]
    reason: str | None
    options: list[str] | None
    operation: str | None
    files: list[str] | None
    description: str | None


class WorkState(TypedDict):
    # Task information
    task_description: str
    plan_ref: str

    # Iteration tracking
    iteration: int
    max_iterations: int
    tool_call_budget: int

    # Error state
    error_baseline: list[dict]
    error_current: list[dict]
    error_delta: str

    # Context
    context_pack_path: str
    relevant_learnings: str

    # LLM output
    work_intent: WorkIntent | None
    llm_response: str

    # Control
    approved: bool
    session_id: str
