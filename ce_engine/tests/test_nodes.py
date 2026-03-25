"""Tests for ce_engine.nodes intent parsing and CLI input validation."""

import pytest

from ce_engine.cli import _validate_plan_ref, _validate_task_description
from ce_engine.nodes import _parse_intent


class TestParseIntent:
    def test_last_line_is_json(self) -> None:
        output = 'Some explanation\nabout the work\n{"intent": "done"}'
        intent = _parse_intent(output)
        assert intent.intent == "done"

    def test_last_line_not_json_scans_backward(self) -> None:
        """When last line is not JSON, parser should scan backwards."""
        output = 'First line\nSecond line\n{"intent": "continue", "reason": "more work needed"}'
        intent = _parse_intent(output)
        assert intent.intent == "continue"
        assert intent.reason == "more work needed"

    def test_no_json_returns_continue(self) -> None:
        output = "Just some text with no JSON at all"
        intent = _parse_intent(output)
        assert intent.intent == "continue"

    def test_empty_output_returns_continue(self) -> None:
        intent = _parse_intent("")
        assert intent.intent == "continue"

    def test_all_lines_json_uses_last(self) -> None:
        output = '{"intent": "blocked"}\n{"intent": "done"}'
        intent = _parse_intent(output)
        assert intent.intent == "done"

    def test_intent_with_all_fields(self) -> None:
        output = '{"intent": "risky_operation", "operation": "rm -rf /tmp", "files": ["a.txt"]}'
        intent = _parse_intent(output)
        assert intent.intent == "risky_operation"
        assert intent.operation == "rm -rf /tmp"
        assert intent.files == ["a.txt"]

    def test_plan_gap_intent(self) -> None:
        output = 'Some work done here\n{"intent": "plan_gap", "description": "Missing tests"}'
        intent = _parse_intent(output)
        assert intent.intent == "plan_gap"
        assert intent.description == "Missing tests"


class TestValidatePlanRef:
    def test_valid_relative_path(self, tmp_path: pytest.TempPathFactory) -> None:
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Plan")
        result = _validate_plan_ref("plan.md")
        assert result.name == "plan.md"

    def test_valid_subdirectory_path(self, tmp_path: pytest.TempPathFactory) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        plan_file = subdir / "plan.md"
        plan_file.write_text("# Plan")
        result = _validate_plan_ref("sub/plan.md")
        assert result.name == "plan.md"

    def test_path_traversal_rejected(self) -> None:
        with pytest.raises(SystemExit):
            _validate_plan_ref("../etc/passwd")


class TestValidateTaskDescription:
    def test_valid_short_task(self) -> None:
        result = _validate_task_description("Fix the login bug")
        assert result == "Fix the login bug"

    def test_at_max_length(self) -> None:
        task = "x" * 1000
        result = _validate_task_description(task)
        assert len(result) == 1000

    def test_over_max_length_rejected(self) -> None:
        task = "x" * 1001
        with pytest.raises(SystemExit):
            _validate_task_description(task)
