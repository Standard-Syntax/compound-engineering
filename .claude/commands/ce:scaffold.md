# /ce:scaffold

Generate a new Python 3.13 project skeleton following the standard stack.

## Usage

```
/ce:scaffold <project-name>
/ce:scaffold <project-name> --agent
```

Add `--agent` to include LangGraph and PydanticAI scaffolding.

## Steps

1. Create the project:
   ```
   mkdir <project-name>
   cd <project-name>
   uv init --lib
   uv python pin 3.13
   ```

2. Add standard dependencies:
   ```
   uv add pydantic anyio httpx tenacity
   uv add --dev pytest ruff ty
   ```

3. If the `--agent` flag was given, also add:
   ```
   uv add langgraph langchain-anthropic pydantic-ai anthropic
   ```

4. Add these sections to `pyproject.toml` under the existing content:
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

5. Create the standard directory layout:
   ```
   src/<project-name>/
   src/<project-name>/__init__.py
   tests/
   tests/__init__.py
   tests/test_main.py
   ```

6. If the `--agent` flag was given, also create:
   - `src/<project-name>/state.py` with a placeholder `TypedDict` state schema
   - `src/<project-name>/graph.py` with a placeholder `StateGraph`
   - `src/<project-name>/agents.py` with a placeholder PydanticAI `Agent`

7. Run verification:
   ```
   uv run ruff check src/
   uv run ty check src/
   ```

8. Report: "Project <project-name> scaffolded successfully."
