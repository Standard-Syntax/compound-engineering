"""Tests for ce_engine.graph routing logic and graph building."""

from ce_engine.graph import (
    _route_after_risky_op,
    _route_intent,
    _route_validate,
    build_work_graph,
)
from ce_engine.state import WorkIntent, WorkState, make_continue_intent


class TestRouteIntent:
    def _make_state(self, **overrides):
        """Build a minimal WorkState for testing."""
        defaults = dict(
            task_description="Test task",
            plan_ref="plan.md",
            iteration=0,
            max_iterations=5,
            tool_call_budget=10,
            error_baseline=[],
            error_current=[],
            error_delta="",
            context_pack_path=".context/compound-engineering/context-pack.md",
            relevant_learnings="",
            work_intent=None,
            llm_response=None,
            approved=False,
        )
        defaults.update(overrides)
        return WorkState(**defaults)

    def test_iteration_exceeds_max_routes_to_validate(self) -> None:
        state = self._make_state(iteration=5, max_iterations=5)
        assert _route_intent(state) == "validate_node"

    def test_continue_routes_to_error_compact(self) -> None:
        state = self._make_state(work_intent=make_continue_intent())
        assert _route_intent(state) == "error_compact_node"

    def test_done_routes_to_validate(self) -> None:
        state = self._make_state(
            work_intent=WorkIntent(
                intent="done",
                reason=None,
                options=None,
                operation=None,
                files=None,
                description=None,
            )
        )
        assert _route_intent(state) == "validate_node"

    def test_blocked_routes_to_human_interrupt(self) -> None:
        state = self._make_state(
            work_intent=WorkIntent(
                intent="blocked",
                reason="Need input",
                options=["a", "b"],
                operation=None,
                files=None,
                description=None,
            )
        )
        assert _route_intent(state) == "human_interrupt_node"

    def test_risky_operation_routes_to_interrupt_node(self) -> None:
        state = self._make_state(
            work_intent=WorkIntent(
                intent="risky_operation",
                reason=None,
                options=None,
                operation="rm file.txt",
                files=["file.txt"],
                description=None,
            )
        )
        assert _route_intent(state) == "risky_op_interrupt_node"

    def test_plan_gap_routes_to_plan_gap_node(self) -> None:
        state = self._make_state(
            work_intent=WorkIntent(
                intent="plan_gap",
                reason=None,
                options=None,
                operation=None,
                files=None,
                description="Missing auth handling",
            )
        )
        assert _route_intent(state) == "plan_gap_node"

    def test_no_work_intent_defaults_to_continue(self) -> None:
        state = self._make_state(work_intent=None)
        assert _route_intent(state) == "error_compact_node"


class TestRouteAfterRiskyOp:
    def _make_state(self, approved: bool) -> WorkState:
        return WorkState(
            task_description="Test",
            plan_ref="plan.md",
            iteration=0,
            max_iterations=5,
            tool_call_budget=10,
            error_baseline=[],
            error_current=[],
            error_delta="",
            context_pack_path=".context/compound-engineering/context-pack.md",
            relevant_learnings="",
            work_intent=None,
            llm_response=None,
            approved=approved,
        )

    def test_approved_routes_to_llm_work_node(self) -> None:
        assert _route_after_risky_op(self._make_state(approved=True)) == "llm_work_node"

    def test_not_approved_routes_to_validate(self) -> None:
        assert _route_after_risky_op(self._make_state(approved=False)) == "validate_node"


class TestRouteValidate:
    def _make_state(self, error_delta: str, tests_passed: bool = True) -> WorkState:
        return WorkState(
            task_description="Add feature X",
            plan_ref="plan.md",
            iteration=1,
            max_iterations=5,
            tool_call_budget=10,
            error_baseline=[],
            error_current=[],
            error_delta=error_delta,
            context_pack_path=".context/compound-engineering/context-pack.md",
            relevant_learnings="",
            work_intent=None,
            llm_response=None,
            approved=False,
            tests_passed=tests_passed,
        )

    def test_tests_failed_continues(self) -> None:
        assert (
            _route_validate(
                self._make_state("Tests failed. Fix failing tests before continuing.", tests_passed=False)
            )
            == "llm_work_node"
        )

    def test_other_delta_ends(self) -> None:
        assert _route_validate(self._make_state("Final: 0 ruff errors. ty: clean", tests_passed=True)) == "END"


class TestBuildWorkGraph:
    def test_returns_compiled_graph(self) -> None:
        graph = build_work_graph()
        # Should be a CompiledStateGraph
        assert graph.__class__.__name__ == "CompiledStateGraph"

    def test_graph_has_all_nodes(self) -> None:
        graph = build_work_graph()
        node_names = list(graph.nodes.keys())
        expected = [
            "prefetch_node",
            "llm_work_node",
            "error_compact_node",
            "human_interrupt_node",
            "risky_op_interrupt_node",
            "plan_gap_node",
            "validate_node",
        ]
        for name in expected:
            assert name in node_names, f"Missing node: {name}"
