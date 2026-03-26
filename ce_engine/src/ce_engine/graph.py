"""LangGraph work loop for the CE engine.

StateGraph(WorkState) is used directly with Pydantic BaseModel --
no cast(Any, WorkState) workaround needed. LangGraph coerces automatically.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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


def build_work_graph() -> CompiledStateGraph:
    """Build and compile the work loop graph with a memory checkpointer."""
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

    # NOTE: MemorySaver is process-local. Sessions cannot be resumed across process
    # restarts. For cross-process resumption, replace with a persistent checkpointer
    # such as langgraph.checkpoint.sqlite.SqliteSaver.
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
