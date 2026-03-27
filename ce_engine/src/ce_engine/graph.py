"""LangGraph work loop for the CE work engine."""

import asyncio
import datetime
import logging
import sqlite3
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ce_engine.config import settings
from ce_engine.nodes import (
    compact_progress_node,
    error_compact_node,
    human_interrupt_node,
    llm_work_node,
    phase_compact_node,
    plan_gap_node,
    prefetch_node,
    risky_op_interrupt_node,
    validate_node,
)
from ce_engine.state import WorkState

logger = logging.getLogger(__name__)


def _route_intent(state: WorkState) -> str:
    """Route to the correct node based on the LLM's declared intent.

    This is a Python function. The LLM cannot influence this routing
    decision -- it only produces the WorkIntent that this function reads.
    """
    if state.iteration >= state.max_iterations:
        return "validate_node"

    if state.work_intent is None:
        return "error_compact_node"

    match state.work_intent.intent:
        case "continue":
            return "error_compact_node"
        case "done":
            return "validate_node"
        case "blocked":
            return "human_interrupt_node"
        case "risky_operation":
            return "risky_op_interrupt_node"
        case "plan_gap":
            return "plan_gap_node"
        case "phase_complete":
            return "phase_compact_node"
        case "compact":
            return "compact_progress_node"
        case _:
            return "error_compact_node"


def _route_after_risky_op(state: WorkState) -> str:
    """Proceed only if the human approved the risky operation."""
    return "llm_work_node" if state.approved else "validate_node"


def _route_validate(state: WorkState) -> str:
    """Route to the work loop when tests failed, otherwise terminate."""
    return "llm_work_node" if not state.tests_passed else "END"


def _route_phase_compact(state: WorkState) -> str:
    """Route after phase_compact_node: pause for manual verification or continue."""
    return "human_interrupt_node" if state.manual_verification_pending else "llm_work_node"


def _build_graph() -> CompiledStateGraph:
    """Build the work loop graph (no checkpointer yet)."""
    graph = StateGraph(WorkState)

    graph.add_node("prefetch_node", prefetch_node)
    graph.add_node("llm_work_node", llm_work_node)
    graph.add_node("error_compact_node", error_compact_node)
    graph.add_node("human_interrupt_node", human_interrupt_node)
    graph.add_node("risky_op_interrupt_node", risky_op_interrupt_node)
    graph.add_node("plan_gap_node", plan_gap_node)
    graph.add_node("validate_node", validate_node)
    graph.add_node("phase_compact_node", phase_compact_node)
    graph.add_node("compact_progress_node", compact_progress_node)

    graph.add_edge(START, "prefetch_node")
    graph.add_edge("prefetch_node", "llm_work_node")
    graph.add_conditional_edges("llm_work_node", _route_intent)
    graph.add_edge("error_compact_node", "llm_work_node")
    graph.add_edge("human_interrupt_node", "llm_work_node")
    graph.add_conditional_edges("risky_op_interrupt_node", _route_after_risky_op)
    graph.add_edge("plan_gap_node", "llm_work_node")
    graph.add_conditional_edges("phase_compact_node", _route_phase_compact)
    graph.add_edge("compact_progress_node", "llm_work_node")
    graph.add_conditional_edges("validate_node", _route_validate)

    return graph


def build_work_graph(checkpointer=None) -> CompiledStateGraph:
    """Build and compile the work loop graph with an optional checkpointer.

    Args:
        checkpointer: Checkpointer instance (e.g. AsyncSqliteSaver, MemorySaver).
                      If None, the caller is responsible for providing one via
                      config at invoke time, or the session will not be persistent.

    Returns:
        Compiled graph with the provided checkpointer (or bare graph if None).
    """
    graph = _build_graph()
    return graph.compile(checkpointer=checkpointer)


async def build_work_graph_async() -> CompiledStateGraph:
    """Build the work loop graph with an AsyncSqliteSaver checkpointer.

    Uses aiosqlite.connect() directly in the current event loop.
    Raises an error if no event loop is available.
    """
    db_path = settings.checkpoint_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _cleanup_old_checkpoints(db_path)

    # If a loop exists, use aiosqlite.connect() directly in it.
    # Otherwise, raise -- silent MemorySaver fallback would break resume guarantees.
    try:
        asyncio.get_running_loop()
    except RuntimeError as exc:
        raise RuntimeError(
            "build_work_graph_async() requires an active event loop "
            "(call via anyio.run() or in an async context). "
            "Use build_work_graph(checkpointer) to provide your own checkpointer."
        ) from exc

    # aiosqlite.connect() is thread-safe and can be awaited directly in the
    # running event loop.
    conn = await aiosqlite.connect(str(db_path))
    checkpointer = AsyncSqliteSaver(conn)
    return build_work_graph(checkpointer=checkpointer)


def _cleanup_old_checkpoints(db_path: Path | str) -> None:
    """Delete checkpoint records older than 7 days. Runs at most once per 24h."""
    cleanup_marker = settings.context_pack_path.parent / ".checkpoint_cleanup"
    now = datetime.datetime.now()
    try:
        if cleanup_marker.exists():
            last_cleanup = datetime.datetime.fromtimestamp(cleanup_marker.stat().st_mtime)
            if (now - last_cleanup).total_seconds() < 86400:
                return
    except OSError as exc:
        logger.debug("Could not read cleanup marker: %s", exc)

    cutoff = now - datetime.timedelta(days=7)
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM checkpoint WHERE timestamp < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        conn.close()
        cleanup_marker.touch()
    except sqlite3.Error as exc:
        logger.warning("Checkpoint cleanup failed: %s", exc)
