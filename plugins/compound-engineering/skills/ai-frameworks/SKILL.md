name: ai-frameworks
description: >
  Write idiomatic Python 3.13 AI agent code using LangGraph, PydanticAI, and the Anthropic SDK.
  Use this skill whenever the user is building agents, multi-step AI pipelines, graph-based
  workflows, structured LLM outputs, tool-calling agents, or AI-backed services in Python.
  Trigger on any mention of: LangGraph, PydanticAI, Anthropic SDK, agent, graph, StateGraph,
  tool use, structured output from LLM, RunContext, multi-agent, agentic workflow, AI pipeline,
  or any request to scaffold a Python project that involves calling an LLM. Always use this skill
  alongside python-modern and pydantic-v2 — never in isolation.

# AI Frameworks — LangGraph, PydanticAI, Anthropic SDK

This skill covers agent architecture, tool wiring, structured outputs, and project scaffolding
for Python 3.13+ AI projects. It builds on top of:

- **`python-modern`** — toolchain (`uv`/`ruff`/`ty`), type syntax, async patterns → read that skill first
- **`pydantic-v2`** — `BaseModel`, `Field`, validators, settings → read that skill for all model patterns

Only patterns specific to AI frameworks live here.


## Framework Selection Guide

| Use case | Framework |
|----------|-----------|
| Structured output from a single agent, typed result, dependency injection | **PydanticAI** |
| Multi-node graph, branching logic, checkpointing, human-in-the-loop | **LangGraph** |
| Low-level API control, streaming, custom tool loops, direct SDK access | **Anthropic SDK** |
| PydanticAI agent backed by Anthropic model | **PydanticAI + Anthropic SDK** (PydanticAI wraps it) |
| Complex multi-agent orchestration with state persistence | **LangGraph** (optionally with PydanticAI nodes) |


## Project Setup

### Dependencies by framework

```toml
# pyproject.toml — Anthropic SDK only
dependencies = [
    "anthropic>=0.40",
    "pydantic>=2.0",
]

# pyproject.toml — PydanticAI
dependencies = [
    "pydantic-ai>=0.0.50",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]

# pyproject.toml — LangGraph
dependencies = [
    "langgraph>=0.2",
    "langchain-anthropic>=0.2",
    "pydantic>=2.0",
]

# pyproject.toml — full stack
dependencies = [
    "anthropic>=0.40",
    "pydantic-ai>=0.0.50",
    "langgraph>=0.2",
    "langchain-anthropic>=0.2",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "httpx>=0.27",
    "tenacity>=8.0",
]
```

### Install

```bash
uv init my-agent
cd my-agent
uv add pydantic-ai pydantic-settings   # PydanticAI project
uv add langgraph langchain-anthropic   # LangGraph project
uv add anthropic                       # bare SDK project
uv add --dev pytest pytest-asyncio    # testing
```

### pytest config for async tests

Add to `pyproject.toml` — required for `async def test_*` functions:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### Environment / Settings pattern

Always use `pydantic-settings` for API keys — see `pydantic-v2` skill for `BaseSettings` patterns.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    model: str = "claude-sonnet-4-20250514"

settings = Settings()
```


## Model Names (Anthropic)

| Model | String |
|-------|--------|
| Sonnet 4 (recommended default) | `claude-sonnet-4-20250514` |
| Opus 4 | `claude-opus-4-20250514` |
| Haiku 3.5 | `claude-haiku-3-5-20241022` |

Always use the full versioned string — never `claude-3-sonnet` or bare aliases.


## Reference Files

Read the relevant file(s) before writing code:

| Framework | File | When to read |
|-----------|------|--------------|
| Anthropic SDK | `references/anthropic-sdk.md` | Direct API calls, streaming, tool loops, raw messages |
| PydanticAI | `references/pydanticai.md` | Agent definitions, tools, structured output, deps |
| LangGraph | `references/langgraph.md` | StateGraph, nodes, edges, checkpointing, human-in-the-loop |


## Cross-Cutting Patterns

### Always async

All agent/graph code uses `async def`. Entry points use `asyncio.run()` or `asyncio.TaskGroup`.
See `python-modern` skill for `TaskGroup` and structured concurrency patterns.

### Pydantic models for all structured data

Use `BaseModel` (from `pydantic-v2` skill) for:
- Tool input/output schemas
- LLM structured output types (`result_type` in PydanticAI, tool schemas in raw SDK)
- Graph state nodes (when not using `TypedDict`)
- Settings / config

### Never hard-code API keys

Always load from environment via `BaseSettings`. Never `os.environ["ANTHROPIC_API_KEY"]` inline.

### Retry strategy

Wrap LLM calls with `tenacity` when building raw loops (see `python-modern` / `httpx-async` skill).
PydanticAI and LangGraph handle retries internally — don't double-wrap.


## Presenting Multi-File Scaffolds

When a request involves more than one file (e.g. "scaffold a full project"), use this format:

### 1. Show the directory tree first (inline format only)

When writing to the chat window directly, always open with a tree so the reader knows
what they're about to see. Skip this when using `create_file` + `present_files` — the
file panel serves as the tree.

```
my-agent/
├── pyproject.toml
├── .env.example
└── src/
    ├── settings.py
    ├── agents/
    │   ├── __init__.py
    │   └── researcher.py
    └── graph/
        ├── state.py
        ├── nodes.py
        └── builder.py
```

### 2. Present each file as a separate fenced code block with a path header

Use a comment-style path header as the first line inside the block — the exact format depends
on the file type:

````
```toml
# pyproject.toml
[project]
name = "my-agent"
...
```

```python
# src/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
...
```

```python
# src/agents/researcher.py
from pydantic_ai import Agent, RunContext
...
```
````

### 3. File ordering

Present files in dependency order — things that are imported first:

1. `pyproject.toml`
2. `.env.example`
3. `src/settings.py`
4. Models / shared types
5. Agent definitions (leaf nodes — no internal imports)
6. Graph state, then nodes, then builder
7. `src/main.py` last

### 4. When to use `create_file` instead

If the computer-use tools are available (`create_file`, `present_files`), write actual files
to `/mnt/user-data/outputs/` and use `present_files` to deliver them. Don't use the
inline comment-header format in that case — use real files with real paths.

Use inline comment-header format only when producing code for the chat window directly.


## What to Avoid

| ❌ Avoid | ✅ Use instead |
|---------|--------------|
| `from typing import Optional, List` | `X \| None`, `list[X]` |
| Synchronous `agent.run_sync()` in async context | `await agent.run()` |
| `os.environ["KEY"]` for secrets | `BaseSettings` |
| Bare `claude-3-sonnet` model alias | Full versioned string |
| Manual JSON parsing of LLM output | `result_type=MyModel` (PydanticAI) or tool schema |
| `asyncio.gather()` | `asyncio.TaskGroup` |
| Mutable default in state node (`state["messages"] = []`) | `Annotated` + reducer in LangGraph |
| `class Config` in Pydantic models | `model_config = ConfigDict(...)` |
