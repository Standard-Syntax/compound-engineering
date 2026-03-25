"""Tests for ce_engine.state Pydantic models."""

import pytest
from pydantic_core import ValidationError

from ce_engine.state import (
    RuffError,
    WorkIntent,
    WorkState,
    make_continue_intent,
)


class TestWorkState:
    def test_minimal_valid_state(self) -> None:
        """Test WorkState with only required fields."""
        state = WorkState(
            task_description="Fix the bug",
            plan_ref="plan.md",
        )
        assert state.task_description == "Fix the bug"
        assert state.plan_ref == "plan.md"
        assert state.iteration == 0
        assert state.max_iterations == 5
        assert state.tool_call_budget == 10

    def test_full_state(self) -> None:
        """Test WorkState with all fields."""
        state = WorkState(
            task_description="Refactor the module",
            plan_ref="plan.md",
            iteration=2,
            max_iterations=5,
            tool_call_budget=10,
            error_baseline=[],
            error_current=[],
            error_delta="No errors found.",
            context_pack_path=".context/compound-engineering/context-pack.md",
            relevant_learnings="",
            work_intent=None,
            llm_response=None,
            approved=False,
        )
        assert state.iteration == 2
        assert state.approved is False

    def test_serialization_roundtrip(self) -> None:
        """Test model_dump and model_validate roundtrip."""
        original = WorkState(
            task_description="Test task",
            plan_ref="plan.md",
            iteration=1,
            error_baseline=[RuffError(file="a.py", line=1, col=0, code="F401", message="unused")],
            error_current=[RuffError(file="a.py", line=1, col=0, code="F401", message="unused")],
            error_delta="1 error remaining.",
            work_intent=make_continue_intent(),
        )
        data = original.model_dump()
        restored = WorkState.model_validate(data)
        assert restored.task_description == original.task_description
        assert restored.iteration == original.iteration
        assert restored.error_delta == original.error_delta

    def test_from_dict_like(self) -> None:
        """Test WorkState can be constructed from a dict-like source."""
        data = {
            "task_description": "Build feature X",
            "plan_ref": "plan.md",
        }
        state = WorkState(**data)
        assert state.task_description == "Build feature X"


class TestWorkIntent:
    def test_continue_intent(self) -> None:
        intent = make_continue_intent()
        assert intent.intent == "continue"
        assert intent.reason is None
        assert intent.options is None

    def test_blocked_intent(self) -> None:
        intent = WorkIntent(
            intent="blocked",
            reason="Need clarification",
            options=["opt1", "opt2"],
            operation=None,
            files=None,
            description=None,
        )
        assert intent.intent == "blocked"
        assert intent.reason == "Need clarification"
        assert intent.options == ["opt1", "opt2"]

    def test_risky_operation_intent(self) -> None:
        intent = WorkIntent(
            intent="risky_operation",
            reason=None,
            options=None,
            operation="rm -rf /tmp/*",
            files=["/tmp/a.txt"],
            description=None,
        )
        assert intent.intent == "risky_operation"
        assert intent.operation == "rm -rf /tmp/*"

    def test_plan_gap_intent(self) -> None:
        intent = WorkIntent(
            intent="plan_gap",
            reason=None,
            options=None,
            operation=None,
            files=None,
            description="Missing error handling for network failures",
        )
        assert intent.intent == "plan_gap"
        assert "network" in intent.description

    def test_invalid_intent_rejected(self) -> None:
        """Test that invalid intent values are rejected by Pydantic."""
        with pytest.raises(ValueError):
            WorkIntent(
                intent="invalid_intent",  # type: ignore
                reason=None,
                options=None,
                operation=None,
                files=None,
                description=None,
            )


class TestRuffError:
    def test_extra_fields_allowed(self) -> None:
        """Ruff can add new fields; we must not reject them."""
        error = RuffError(
            file="src/app.py",
            line=10,
            col=5,
            code="E501",
            message="line too long",
            unknown_field="should be ignored",
        )
        assert error.code == "E501"
        assert error.file == "src/app.py"

    def test_minimal_ruff_error(self) -> None:
        """Test RuffError with just the required fields."""
        error = RuffError(file="a.py", line=1, col=0, code="F401", message="unused import")
        assert error.code == "F401"

    def test_serialization(self) -> None:
        """Test RuffError serializes to JSON-compatible dict."""
        error = RuffError(file="b.py", line=5, col=2, code="E302", message="expected blank line")
        data = error.model_dump()
        assert data["file"] == "b.py"
        assert data["code"] == "E302"
        # Extra fields should be present
        assert "unknown_extra" not in data


class TestMakeContinueIntent:
    def test_returns_work_intent(self) -> None:
        intent = make_continue_intent()
        assert isinstance(intent, WorkIntent)

    def test_is_frozen(self) -> None:
        """make_continue_intent returns a frozen/immutable intent.

        Pydantic frozen models raise ValidationError on mutation, not TypeError.
        """
        intent = make_continue_intent()
        with pytest.raises(ValidationError):
            intent.intent = "done"  # type: ignore
