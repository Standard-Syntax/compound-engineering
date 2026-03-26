"""Shared test utilities for ce_engine tests."""

from pathlib import Path

from ce_engine.state import WorkState


def make_test_state(**overrides: object) -> WorkState:
    """Build a minimal WorkState for testing.

    Provides sensible defaults for all required fields. Override any field
    via keyword arguments.
    """
    defaults: dict[str, object] = {
        "task_description": "Test task",
        "plan_ref": "plan.md",
        "iteration": 0,
        "max_iterations": 5,
        "tool_call_budget": 10,
        "error_baseline": [],
        "error_current": [],
        "error_delta": "",
        "context_pack_path": Path(".context/compound-engineering/context-pack.md"),
        "relevant_learnings": "",
        "work_intent": None,
        "llm_response": None,
        "approved": False,
        "tests_passed": True,
    }
    defaults.update(overrides)
    return WorkState(**defaults)
