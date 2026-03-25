"""Integration tests for the compiled work graph.

These tests verify that the graph wiring (edges, routing, state flow)
works end-to-end without testing LLM quality.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from ce_engine.graph import build_work_graph
from ce_engine.state import RuffError, WorkState
from ce_engine.toolchain import CommandResult


class TestGraphWiring:
    """Tests that graph wiring is correct end-to-end."""

    @pytest.mark.asyncio
    async def test_graph_completes_with_done_intent(self, tmp_path: Path) -> None:
        """Monkeypatch external tool calls; let real file I/O write to tmp_path."""
        graph = build_work_graph()

        async def mock_ruff_check(path: str = ".") -> list[RuffError]:
            return []

        async def mock_ty_check(path: str = ".") -> str:
            return ""

        async def mock_call_llm(prompt: str) -> str:
            return '{"intent": "done"}'

        async def mock_run_command(cmd: list[str], timeout: float = 30.0) -> CommandResult:
            if cmd == ["git", "branch", "--show-current"]:
                return CommandResult(returncode=0, stdout="main", stderr="")
            if cmd == ["git", "diff", "--name-only", "HEAD"]:
                return CommandResult(returncode=0, stdout="", stderr="")
            return CommandResult(returncode=0, stdout="", stderr="")

        # Monkeypatch the learnings_path and context_pack_path to use tmp_path
        # so file writes don't pollute the real filesystem
        context_pack = tmp_path / "context-pack.md"
        learnings_dir = tmp_path / "learnings"
        learnings_dir.mkdir(parents=True, exist_ok=True)

        state = WorkState(
            task_description="test task",
            plan_ref="plan.md",
            iteration=0,
            max_iterations=3,
            tool_call_budget=10,
            error_baseline=[],
            error_current=[],
            error_delta="",
            context_pack_path=str(context_pack),
            relevant_learnings="",
            work_intent=None,
            llm_response="",
            approved=False,
        )

        config = {"configurable": {"thread_id": "test-thread"}}

        with (
            patch("ce_engine.nodes.run_ruff_check", mock_ruff_check),
            patch("ce_engine.nodes.run_ty_check", mock_ty_check),
            patch("ce_engine.nodes.run_command", mock_run_command),
            patch("ce_engine.nodes._call_llm", mock_call_llm),
            patch("ce_engine.nodes.settings") as mock_settings,
        ):
            mock_settings.learnings_path = learnings_dir
            mock_settings.context_pack_path = context_pack
            mock_settings.git_timeout = 5.0
            mock_settings.lint_timeout = 5.0
            result = await graph.ainvoke(state, config)

        # Graph should complete without raising
        assert result is not None
        # Final intent should be done
        if result.get("work_intent"):
            assert result["work_intent"].intent == "done"
