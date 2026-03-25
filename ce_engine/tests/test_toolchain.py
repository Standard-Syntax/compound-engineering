"""Tests for ce_engine.toolchain subprocess runners."""

from unittest.mock import AsyncMock, patch

import pytest

from ce_engine.state import RuffError
from ce_engine.toolchain import (
    CommandResult,
    compute_error_delta,
    run_ruff_check,
    run_ty_check,
)


class TestComputeErrorDelta:
    """Tests for compute_error_delta."""

    def _make_error(self, file: str, line: int, code: str) -> RuffError:
        return RuffError(file=file, line=line, col=0, code=code, message="")

    def test_all_resolved(self) -> None:
        baseline = [
            self._make_error("a.py", 10, "E501"),
            self._make_error("a.py", 20, "E501"),
        ]
        current: list[RuffError] = []
        result = compute_error_delta(baseline, current)
        assert "2 errors resolved" in result
        assert "0 new errors introduced" in result
        assert "0 total remaining" in result

    def test_all_introduced(self) -> None:
        baseline: list[RuffError] = []
        current = [
            self._make_error("a.py", 10, "E501"),
            self._make_error("a.py", 20, "E501"),
        ]
        result = compute_error_delta(baseline, current)
        assert "0 errors resolved" in result
        assert "2 new errors introduced" in result
        assert "2 total remaining" in result

    def test_mixed_resolved_and_introduced(self) -> None:
        baseline = [
            self._make_error("a.py", 10, "E501"),
            self._make_error("a.py", 20, "E501"),
            self._make_error("a.py", 30, "E501"),
        ]
        current = [
            self._make_error("a.py", 10, "E501"),  # still present
            self._make_error("b.py", 15, "E501"),  # introduced
        ]
        result = compute_error_delta(baseline, current)
        assert "2 errors resolved" in result
        assert "1 new errors introduced" in result
        assert "2 total remaining" in result

    def test_same_count_different_errors(self) -> None:
        # Same count, but completely different errors — all 2 baseline resolved, 2 new introduced
        baseline = [
            self._make_error("a.py", 10, "E501"),
            self._make_error("a.py", 20, "E501"),
        ]
        current = [
            self._make_error("b.py", 10, "E501"),
            self._make_error("b.py", 20, "E501"),
        ]
        result = compute_error_delta(baseline, current)
        assert "2 errors resolved" in result
        assert "2 new errors introduced" in result

    def test_moved_error_counted_as_resolved_and_introduced(self) -> None:
        # Same file, same code, but different line — counts as resolved + introduced
        baseline = [self._make_error("a.py", 10, "E501")]
        current = [self._make_error("a.py", 15, "E501")]
        result = compute_error_delta(baseline, current)
        assert "1 errors resolved" in result
        assert "1 new errors introduced" in result
        assert "1 total remaining" in result

    def test_no_errors(self) -> None:
        result = compute_error_delta([], [])
        assert "0 errors resolved" in result
        assert "0 new errors introduced" in result
        assert "0 total remaining" in result

    def test_empty_baseline(self) -> None:
        current = [self._make_error("a.py", 10, "E501")]
        result = compute_error_delta([], current)
        assert "0 errors resolved" in result
        assert "1 new errors introduced" in result


class TestRunRuffCheck:
    """Tests for run_ruff_check."""

    @pytest.mark.asyncio
    async def test_empty_output_returns_empty_list(self) -> None:
        with patch("ce_engine.toolchain.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = CommandResult(returncode=0, stdout="", stderr="")
            result = await run_ruff_check(".")
            assert result == []

    @pytest.mark.asyncio
    async def test_valid_json_parsed(self) -> None:
        with patch("ce_engine.toolchain.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = CommandResult(
                returncode=1,
                stdout="["
                '{"file":"a.py","line":10,"col":0,"code":"E501","message":"line too long"}'
                "]",
                stderr="",
            )
            result = await run_ruff_check(".")
            assert len(result) == 1
            assert result[0].file == "a.py"
            assert result[0].line == 10
            assert result[0].code == "E501"

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty_list(self) -> None:
        with patch("ce_engine.toolchain.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = CommandResult(
                returncode=1,
                stdout="not valid json{",
                stderr="",
            )
            result = await run_ruff_check(".")
            assert result == []


class TestRunTyCheck:
    """Tests for run_ty_check."""

    @pytest.mark.asyncio
    async def test_clean_returns_empty_string(self) -> None:
        with patch("ce_engine.toolchain.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = CommandResult(returncode=0, stdout="", stderr="")
            result = await run_ty_check(".")
            assert result == ""

    @pytest.mark.asyncio
    async def test_errors_return_output(self) -> None:
        with patch("ce_engine.toolchain.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = CommandResult(
                returncode=1,
                stdout="",
                stderr="error: Cannot find implementation",
            )
            result = await run_ty_check(".")
            assert "Cannot find implementation" in result
