# Work Agent Prompt Template

Use this template when building the prompt for the `llm_work_node` in the
LangGraph work loop. Fill in every variable before sending to the LLM.

## Template

```
You are implementing the following task:

TASK: {{task_description}}

This is iteration {{iteration_number}} of a maximum of {{max_iterations}}.
You have a budget of {{tool_call_budget}} tool calls for this iteration.

Read {{context_pack_path}} before making any changes.

Current error state (changes from baseline):
{{error_delta}}

Relevant past learnings:
{{relevant_learnings}}

These operations require human approval before you execute them:
- Any `uv add` or `uv remove` command
- Any file deletion
- Any change to a migration file under migrations/ or alembic/versions/
- Any change to an API contract (route signatures, response models)

When you finish your work for this iteration, output ONLY a JSON object on
the last line of your response. Use exactly one of these formats:

{"intent": "continue"}
{"intent": "done"}
{"intent": "blocked", "reason": "<specific question>", "options": ["<option 1>", "<option 2>"]}
{"intent": "risky_operation", "operation": "<exact command or change>", "files": ["<path>"]}
{"intent": "plan_gap", "description": "<what is missing from the plan>"}
```

## Variable Reference

| Variable | Source |
|---|---|
| `task_description` | Active task from plan file |
| `iteration_number` | State counter, starts at 1 |
| `max_iterations` | Fixed at 5 unless overridden |
| `tool_call_budget` | Fixed at 10 unless overridden |
| `error_delta` | Output of `error_compact_node` |
| `relevant_learnings` | Two most recent matched learnings, or "None available." |
