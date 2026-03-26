name: python-modern
description: >
  Write idiomatic Python 3.13 code using modern syntax, type annotations, and the uv/ruff/ty
  toolchain. Use this skill whenever writing, reviewing, or scaffolding Python code — especially
  for new projects, modules, scripts, CLI tools, or any task where Python is involved. Trigger
  on any Python request: "write a script", "create a Python module", "set up a Python project",
  "help me type-annotate this", "how should I structure this in Python", or any code generation
  that will run on Python 3.13+. Always use this skill instead of relying on older Python patterns.

# Python 3.13 — Modern Syntax, Types & Toolchain

This skill ensures all Python code Claude writes targets Python 3.13+ idioms, uses the modern
type system fully, and is set up with the `uv` / `ruff` / `ty` toolchain by default.


## Toolchain

| Tool | Role | Install |
|------|------|---------|
| `uv` | Package manager, venv, script runner | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `ruff` | Linter + formatter (replaces black, isort, flake8) | managed via `uv` |
| `ty` | Type checker (Astral, replaces mypy for new projects) | managed via `uv` |

Always manage packages with `uv`. Never suggest `pip install` directly to the user.


## Project Setup

### New project

```bash
uv init my-project          # creates pyproject.toml, .python-version, src layout
cd my-project
uv add ruff ty               # add dev tools
uv run python main.py        # run without activating venv
```

### pyproject.toml template

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = ["ruff>=0.9", "ty>=0.0.1a1"]

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TCH"]
# "I" enforces import ordering (stdlib → third-party → local). Run `ruff check --fix` to auto-correct.

[tool.ruff.format]
quote-style = "double"

[tool.ty]
python-version = "3.13"
```

### .python-version

```
3.13
```


## Modern Type Syntax (3.10+, preferred in 3.13)

Use built-in generic types — never import from `typing` for these:

```python
# ✅ modern
def process(items: list[str]) -> dict[str, int]: ...
def find(val: str | None) -> str | None: ...

# ❌ old
from typing import List, Dict, Optional, Union
def process(items: List[str]) -> Dict[str, int]: ...
def find(val: Optional[str]) -> Optional[str]: ...
```

### Type aliases — use `type` statement (3.12+)

Prefer `type` aliases over `TypeVar` for named type shortcuts:

```python
type Vector = list[float]
type Matrix = list[list[float]]
type UserId = int
type PositiveInt = int  # semantic marker, no runtime effect
```

For generic aliases that need type parameters, use `type` with `[T]`:

```python
type Pair[T] = tuple[T, T]
type StrDict[T] = dict[str, T]
```

### Generics — use new syntax (3.12+)

```python
# ✅ modern
def first[T](items: list[T]) -> T:
    return items[0]

class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
    def push(self, item: T) -> None:
        self._items.append(item)
    def pop(self) -> T:
        return self._items.pop()
```

### TypedDict vs dataclass

**Use `dataclass(slots=True, frozen=True)`** for internal models — your own data structures,
return types, config objects. Prefer this by default.

**Use `TypedDict`** only when the value must stay a plain `dict` at runtime — e.g. a raw JSON
payload, a kwargs dict, or an external API response you're not transforming.

```python
from dataclasses import dataclass, field

@dataclass(slots=True, frozen=True)
class Config:
    host: str
    port: int = 8080
    tags: list[str] = field(default_factory=list)
```

```python
from typing import TypedDict  # still imported from typing — no builtin equivalent

class UserPayload(TypedDict):
    id: int
    name: str
    email: str
```

### Still import from `typing`

These have no builtin equivalent — always import them from `typing`:
`TypedDict`, `Protocol`, `runtime_checkable`, `cast`, `overload`, `TYPE_CHECKING`

Everything else (`List`, `Dict`, `Optional`, `Union`, `Tuple`, `Type`) is replaced by
builtins and `|` syntax — never import those.

### Protocol for structural typing

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Readable(Protocol):
    def read(self) -> str: ...
```


## Python 3.13 Syntax Highlights

### f-string improvements (3.12+)

```python
# Nested quotes — no escaping needed
name = "world"
msg = f"Hello {f'{name!r}'}"

# Multi-line f-strings
query = (
    f"SELECT * FROM {table!r} "
    f"WHERE id = {record_id}"
)
```

### Exception groups and `except*` (3.11+)

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_a())
        tg.create_task(fetch_b())
except* ValueError as eg:
    for exc in eg.exceptions:
        print(f"ValueError: {exc}")
```

### `tomllib` for config (stdlib, 3.11+)

Always use `tomllib` to read TOML files — no third-party dependency needed:

```python
import tomllib

with open("pyproject.toml", "rb") as f:
    config = tomllib.load(f)
```

Always open in binary mode (`"rb"`). For writing TOML, use `tomli` (install via `uv add tomli`).

### `pathlib` always over `os.path`

```python
from pathlib import Path

root = Path(__file__).parent
config_path = root / "config" / "settings.toml"
data = config_path.read_text()
```


## Async Patterns

Use `asyncio.TaskGroup` instead of `gather` for structured concurrency. When any task in
the group raises, `TaskGroup` cancels remaining tasks and surfaces the exception via `except*`
(not a plain `except`):

```python
import asyncio

async def main() -> None:
    async with asyncio.TaskGroup() as tg:
        task_a = tg.create_task(fetch("https://example.com/a"))
        task_b = tg.create_task(fetch("https://example.com/b"))
    # both tasks are done here; both succeed — no bare except needed

# Handle errors from TaskGroup:
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(unreliable())
except* ValueError as eg:
    for exc in eg.exceptions:
        print(f"ValueError: {exc}")
except* BaseException as eg:
    print(f"Other error: {eg.exceptions}")
```

The `except*` variant (3.11+) is required — plain `except` won't catch `ExceptionGroup` from
`TaskGroup`. Handle specific exception types with `except*` before falling back to `except* BaseException`.


## HTTP + Retry Pattern

Use `httpx` for async HTTP and `tenacity` for retry logic. Always import both at module level.

```toml
# pyproject.toml
dependencies = ["httpx", "tenacity"]
```

```python
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(url)
```

For PEP 723 inline scripts, still import at the top — never inside functions:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx", "tenacity"]
# ///

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
```


## What to Avoid

| Avoid | Use instead |
|-------|-------------|
| `from typing import List, Dict, Optional, Union` | Built-in `list`, `dict`, `X \| None`, `X \| Y` |
| `TypeVar("T")` | `[T]` in function/class signature |
| `pip install` | `uv add` |
| `python -m venv` | `uv venv` or just `uv run` |
| `black`, `isort`, `flake8` | `ruff format`, `ruff check` |
| `mypy` (new projects) | `ty check` |
| `os.path.join(...)` | `Path(...) / ...` |
| `tomllib`-blocking alternatives (`toml` pkg, `tomliw`) | `tomllib` (stdlib, 3.11+) — binary-mode open |
| `asyncio.gather(...)` | `asyncio.TaskGroup` + `except*` for error handling |
| `time.sleep` in retry loops | `tenacity` decorators |
| Imports inside functions | Module-level imports always |


## Running and Checking

```bash
uv run python -m my_module    # run
uv run ruff check .           # lint
uv run ruff format .          # format
uv run ty check               # type check
```

For standalone scripts (no project needed):

```bash
uv run --python 3.13 script.py
```

### PEP 723 Inline Scripts

For single-file scripts with dependencies, use the PEP 723 inline script header.
All dependency and metadata declarations go in the header block before any imports:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx>=2.0", "tenacity", "rich"]
# ///

import httpx
from rich import print
from tenacity import retry, stop_after_attempt, wait_exponential

# ... rest of script
```

Run with `uv run script.py` — no project or venv setup required. Dependencies are
managed by `uv` automatically. The header format is `# /// script` ... `# ///` on its own line.
