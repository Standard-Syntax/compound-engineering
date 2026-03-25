from typing import cast

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ce_engine.nodes import (
    error_compact_node,
    human_interrupt_node,
    llm_work_node,
    plan_gap_node,
    prefetch_node,
    risky_op_interrupt_node,
    validate_node,
)
from ce_engine.state import WorkState


def _route_intent(state: WorkState) -> str:
    """Route to the correct node based on the LLM's declared intent.

    This is a Python function. The LLM cannot influence this routing
    decision — it only produces the WorkIntent that this function reads.
    """
    if state["iteration"] >= state["max_iterations"]:
        return "validate_node"

    intent = state["work_intent"]["intent"] if state["work_intent"] else "continue"

    match intent:
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
        case _:
            return "error_compact_node"


def _route_after_risky_op(state: WorkState) -> str:
    """Proceed only if the human approved the risky operation."""
    return "llm_work_node" if state["approved"] else "validate_node"


def build_work_graph() -> CompiledStateGraph:
    """Build and compile the work loop graph with a memory checkpointer."""
    graph = StateGraph(cast(Any, WorkState))

    graph.add_node("prefetch_node", prefetch_node)
    graph.add_node("llm_work_node", llm_work_node)
    graph.add_node("error_compact_node", error_compact_node)
    graph.add_node("human_interrupt_node", human_interrupt_node)
    graph.add_node("risky_op_interrupt_node", risky_op_interrupt_node)
    graph.add_node("plan_gap_node", plan_gap_node)
    graph.add_node("validate_node", validate_node)

    graph.add_edge(START, "prefetch_node")
    graph.add_edge("prefetch_node", "llm_work_node")
    graph.add_conditional_edges("llm_work_node", _route_intent)
    graph.add_edge("error_compact_node", "llm_work_node")
    graph.add_edge("human_interrupt_node", "llm_work_node")
    graph.add_conditional_edges("risky_op_interrupt_node", _route_after_risky_op)
    graph.add_edge("plan_gap_node", "llm_work_node")
    graph.add_edge("validate_node", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
