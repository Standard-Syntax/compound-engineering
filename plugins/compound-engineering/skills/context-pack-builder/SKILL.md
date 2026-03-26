# Context Pack Builder

The Context Pack is a structured file written before any LLM agent call.
It contains all pre-fetched project state so agents do not waste tool calls
rediscovering known information.

## Building a Context Pack

Before dispatching any agent, run these commands and collect their output:

1. `ruff check --output-format=json .` — capture as `ruff_errors`
2. `ty check .` — capture as `ty_errors`
3. Read `pyproject.toml` — extract `python`, `dependencies`, and `[tool.*]` sections
4. Read the active plan file from `.context/compound-engineering/plan/`
5. Read the two most recently modified files in `.context/compound-engineering/learnings/`

Write the collected data to `.context/compound-engineering/context-pack.md`
using this template:

```xml
<project>
  python: <version from pyproject.toml>
  package_manager: uv
  linter: ruff
  type_checker: ty
  frameworks: <list from dependencies>
</project>

<current_task>
  branch: <current git branch>
  changed_files: <output of git diff --name-only HEAD>
  plan_ref: <path to active plan file>
  task: <active task description from plan>
</current_task>

<pre_fetched>
  ruff_errors: |
    <ruff_errors output>
  ty_errors: |
    <ty_errors output>
</pre_fetched>

<relevant_learnings>
  <summary of two most recent learnings>
</relevant_learnings>
```

## Rules

- Write the Context Pack to disk before dispatching any agent.
- Every agent prompt must include the line:
  `Read .context/compound-engineering/context-pack.md before starting.`
- Never include secrets, API keys, or `.env` file contents in the pack.
