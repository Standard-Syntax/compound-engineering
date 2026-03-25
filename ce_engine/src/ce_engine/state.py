"""Pydantic v2 state models for the CE work engine.

WorkState is the graph-level state -- passed to every node.
WorkIntent captures the LLM's declared intent for the current iteration.
RuffError models ruff's JSON output format with forward-compat via extra="allow".
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuffError(BaseModel):
    """Model for ruff check JSON output.

    extra="allow" provides forward-compat with future ruff versions
    that may add new fields.
    """

    model_config = ConfigDict(extra="allow")

    file: str
    line: int
    col: int
    code: str
    message: str


class WorkIntent(BaseModel):
    """LLM-declared intent for the current iteration.

    Frozen to prevent accidental mutation during graph execution.
    """

    model_config = ConfigDict(frozen=True)

    intent: Literal["continue", "done", "blocked", "risky_operation", "plan_gap"]
    reason: str | None = None
    options: list[str] | None = None
    operation: str | None = None
    files: list[str] | None = None
    description: str | None = None


class WorkState(BaseModel):
    """Graph-level state passed to every node."""

    model_config = ConfigDict(extra="allow")

    # Task information
    task_description: str = ""
    plan_ref: str = ""

    # Iteration tracking
    iteration: int = 0
    max_iterations: int = 5
    tool_call_budget: int = 10

    # Error state
    error_baseline: list[RuffError] = Field(default_factory=list)
    error_current: list[RuffError] = Field(default_factory=list)
    error_delta: str = ""

    # Context
    context_pack_path: Path = Path(".context/compound-engineering/context-pack.md")
    relevant_learnings: str = ""

    # LLM output
    work_intent: WorkIntent | None = None
    llm_response: str | None = None

    # Control
    approved: bool = False
    session_id: str = ""


def make_continue_intent() -> WorkIntent:
    """Factory for a default 'continue' intent.

    Replaces the mutable _EMPTY_INTENT dict pattern.
    """
    return WorkIntent(intent="continue")
