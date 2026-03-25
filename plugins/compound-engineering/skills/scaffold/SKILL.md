---
name: scaffold
description: Generate a new Python 3.13 project skeleton following the standard stack
argument-hint: "<project-name> [--agent]"
version: "1.0.0"
triggers: ["ce:scaffold", "scaffold"]
---

# Generate a new Python 3.13 project skeleton

## Introduction

Generate a new Python 3.13 project skeleton following the standard stack. Use this when the user asks to create a new project scaffold.

## Usage

```
scaffold <project-name>
scaffold <project-name> --agent
```

Add `--agent` to include LangGraph and PydanticAI scaffolding.

## Steps

### 1. Parse arguments

Extract `<project-name>` and check for the `--agent` flag. If no project name is provided, ask the user.

### 2. Create the project

Run the following commands:

```bash
mkdir <project-name>
cd <project-name>
uv init --lib
uv python pin 3.13
```

### 3. Add standard dependencies

```bash
uv add pydantic anyio httpx tenacity
uv add --dev pytest ruff ty
```

### 4. Add agent dependencies (if `--agent` flag given)

If the `--agent` flag was provided, also run:

```bash
uv add langgraph langchain-anthropic pydantic-ai anthropic
```

### 5. Configure pyproject.toml

Add these sections to `pyproject.toml` under the existing content:

```toml
[tool.ruff]
target-version = "py313"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "ANN"]
fixable = ["I", "UP"]

[tool.ty]
python-version = "3.13"
```

### 6. Create the standard directory layout

Create the following files and directories:

```
src/<project-name>/
src/<project-name>/__init__.py
tests/
tests/__init__.py
tests/test_main.py
```

### 7. Create agent-specific files (if `--agent` flag given)

If the `--agent` flag was provided, also create:

- `src/<project-name>/state.py` with a placeholder `TypedDict` state schema
- `src/<project-name>/graph.py` with a placeholder `StateGraph`
- `src/<project-name>/agents.py` with a placeholder PydanticAI `Agent`

### 8. Run verification

```bash
uv run ruff check src/
uv run ty check src/
```

### 9. Report

Report: "Project `<project-name>` scaffolded successfully."
