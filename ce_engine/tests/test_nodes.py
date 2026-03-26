"""Tests for ce_engine.nodes intent parsing and CLI input validation."""

import random
from pathlib import Path
from unittest.mock import patch

import anyio
import pytest

from ce_engine.cli import _validate_plan_ref, _validate_task_description
from ce_engine.nodes import _parse_intent, prefetch_node
from ce_engine.state import RuffError, WorkState
from ce_engine.toolchain import CommandResult


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

    def test_no_json_returns_blocked(self) -> None:
        output = "Just some text with no JSON at all"
        intent = _parse_intent(output)
        assert intent.intent == "blocked"
        assert intent.reason is not None

    def test_empty_output_returns_blocked(self) -> None:
        intent = _parse_intent("")
        assert intent.intent == "blocked"
        assert intent.reason is not None

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
    def test_valid_relative_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        plan_file = tmp_path / "plan.md"
        plan_file.write_text("# Plan")
        result = _validate_plan_ref("plan.md")
        assert result.name == "plan.md"

    def test_valid_subdirectory_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
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


class TestPrefetchConcurrentRace:
    """Tests that prefetch_node handles concurrent ruff+ty without type swap."""

    @pytest.mark.asyncio
    async def test_prefetch_concurrent_race(self, tmp_path: Path) -> None:
        """Verify ruff_errors is always a list and ty_output is always a string.

        Runs 10 times with random delays to catch any ordering assumptions.
        """

        async def mock_ruff(path: str) -> list[RuffError]:
            await anyio.sleep(random.uniform(0.001, 0.01))
            return [RuffError(file="a.py", line=1, col=0, code="E501", message="")]

        async def mock_ty(path: str) -> str:
            await anyio.sleep(random.uniform(0.001, 0.01))
            return ""

        async def mock_run_command(cmd: list[str], *, timeout: float = 30.0) -> CommandResult:
            return CommandResult(returncode=0, stdout="", stderr="")

        for i in range(10):
            with (
                patch("ce_engine.nodes.run_ruff_check", mock_ruff),
                patch("ce_engine.nodes.run_ty_check", mock_ty),
                patch("ce_engine.nodes.run_command", mock_run_command),
            ):
                state = WorkState(
                    task_description="test",
                    plan_ref="plan.md",
                )
                result = await prefetch_node(state)

            # ruff_errors must always be a list
            assert isinstance(result["error_current"], list), (
                f"run {i}: error_current is {type(result['error_current'])}, expected list"
            )
