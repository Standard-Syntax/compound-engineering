# ce_engine

LangGraph work execution engine for Compound Engineering. Given a task description and plan reference, the engine iteratively runs lint checks, LLM inference, and test validation until the work is complete or a human interrupt is required.

## Stack

- **Runtime**: Python 3.13, `uv`
- **AI**: LangGraph + `langchain-anthropic`
- **State**: Pydantic v2 models
- **Async**: `anyio` (structured concurrency)
- **Retry**: `tenacity` (exponential backoff on LLM calls)

## Running

```bash
cd ce_engine
uv sync
uv run ce-work '<task_description>' <plan_ref> [session_id]
```

## Testing

```bash
cd ce_engine
PYTHONPATH=src uv run pytest -v
```

## Development

```bash
uv run ruff check src/ tests/
uv run ty check src/
uv run ruff format src/ tests/
```
