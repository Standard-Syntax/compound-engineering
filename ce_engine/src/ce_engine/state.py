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

    model_config = ConfigDict(frozen=True, extra="allow")

    file: str
    line: int
    col: int
    code: str
    message: str


class SolutionSummary(BaseModel, frozen=True):
    """Summary of a relevant compound doc for context pack."""

    title: str
    module: str
    root_cause: str
    solution: str
    file_path: str
    relevance_tags: list[str] = Field(default_factory=list)


class WorkIntent(BaseModel):
    """LLM-declared intent for the current iteration.

    Frozen to prevent accidental mutation during graph execution.
    """

    model_config = ConfigDict(frozen=True)

    intent: Literal[
        "continue", "done", "blocked", "risky_operation", "plan_gap", "phase_complete", "compact"
    ]
    reason: str | None = None
    options: list[str] | None = None
    operation: str | None = None
    files: list[str] | None = None
    description: str | None = None


class WorkState(BaseModel):
    """Graph-level state passed to every node."""

    model_config = ConfigDict(extra="ignore")

    # Task information
    task_description: str = ""
    plan_ref: str = ""

    # Iteration tracking
    iteration: int = 0
    max_iterations: int = 5
    tool_call_budget: int = 10

    # Phase tracking
    current_phase: int = 0
    phase_definitions: list[str] = Field(default_factory=list)
    manual_verification_pending: bool = False
    pending_verification_items: list[str] = Field(default_factory=list)
    files_read_count: int = 0

    # Error state
    error_baseline: list[RuffError] = Field(default_factory=list)
    error_current: list[RuffError] = Field(default_factory=list)
    error_delta: str = ""

    # Context
    context_pack_path: Path = Path(".context/compound-engineering/context-pack.md")
    relevant_learnings: str = ""
    relevant_solutions: list[SolutionSummary] = Field(default_factory=list)
    research_artifact_path: str | None = None

    # LLM output
    work_intent: WorkIntent | None = None
    llm_response: str | None = None

    # Control
    approved: bool = False

    # Validation
    tests_passed: bool = True


def make_continue_intent() -> WorkIntent:
    """Factory for a default 'continue' intent.

    Replaces the mutable _EMPTY_INTENT dict pattern.
    """
    return WorkIntent(intent="continue")
