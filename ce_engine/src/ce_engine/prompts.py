"""Prompt templates for the CE work engine."""

from ce_engine.state import WorkState


def build_work_prompt(state: WorkState) -> str:
    """Build the prompt string for the llm_work_node."""
    return (
        f"You are implementing the following task:\n\n"
        f"TASK: {state.task_description}\n\n"
        f"This is iteration {state.iteration} of a maximum of "
        f"{state.max_iterations}.\n"
        f"You have a budget of {state.tool_call_budget} tool calls "
        f"for this iteration.\n\n"
        f"Read {state.context_pack_path} before making any changes.\n\n"
        f"Current error state (changes from baseline):\n"
        f"{state.error_delta}\n\n"
        f"Relevant past learnings:\n"
        f"{state.relevant_learnings or 'None available.'}\n\n"
        "These operations require human approval before you execute them:\n"
        "- Any `uv add` or `uv remove` command\n"
        "- Any file deletion\n"
        "- Any change to a migration file under migrations/ or alembic/versions/\n"
        "- Any change to an API contract (route signatures, response models)\n\n"
        "## Context Budget Guidance\n\n"
        "Context utilization is a core engineering constraint. Keep your context\n"
        "focused and compact:\n\n"
        "- Prefer sub-agents for file reading, test running, and log inspection\n"
        "- Keep context focused on the current phase; do not pre-load files for future phases\n"
        "- If you have read more than 15 files directly in this session, include\n"
        "  [COMPACT] in your response text (not JSON) to trigger compaction before\n"
        "  continuing\n"
        "- Keep context utilization in the 40-60% range; do not let the window fill\n"
        "- When you complete a planned phase from the plan file, include [PHASE_COMPLETE]\n"
        "  in your response text (not JSON) to trigger the phase verification gate\n\n"
        "When you finish your work for this iteration, output ONLY a JSON object\n"
        "on the last line of your response. Use exactly one of these formats:\n\n"
        '{"intent": "continue"}\n'
        '{"intent": "done"}\n'
        '{"intent": "blocked", "reason": "<specific question>", '
        '"options": ["<option 1>", "<option 2>"]}\n'
        '{"intent": "risky_operation", "operation": "<exact command>", '
        '"files": ["<path>"]}\n'
        '{"intent": "plan_gap", "description": "<what is missing>"}\n'
    )
