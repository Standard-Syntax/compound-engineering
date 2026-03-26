name: python-antipatterns
description: >
  Recognize and correct outdated or unsafe Python patterns when writing, reviewing, or refactoring
  Python code. Use this skill whenever Claude might default to legacy syntax — especially when
  fixing bugs, reviewing existing code, adding to an existing file, or when the task involves
  any of: type annotations, HTTP clients, package management, CLI tools, config loading,
  logging, subprocess calls, or async patterns. Triggers on phrases like "fix this", "review
  this code", "add a function", "what's wrong with", "clean this up", "refactor", or any time
  Claude is working with Python that wasn't written for 3.13+. Always use alongside python-modern.
  If you see requests, Optional, Union, List, Dict, pip, poetry, os.path, asyncio.gather,
  logging.basicConfig, subprocess.call, TypeVar, argparse, click, command-line,
  from __future__, time.sleep, tenacity, anyio, httpx, or extra in code you're about to write
  or modify — stop and apply this skill first.

# Python Anti-Patterns — What Claude Must Never Write

This skill is the **negative-space companion** to `python-modern`. That skill tells you what to
write. This one tells you what to *recognize and refuse*. When in doubt, cross-reference both.


## Quick Reference — Banned Patterns

| ❌ Never write | ✅ Write instead |
|----------------|-----------------|
| `from typing import List, Dict, Tuple, Set, Optional, Union, Type` | Built-ins + `\|` syntax |
| `TypeVar("T")` | `[T]` in function/class signature |
| `from __future__ import annotations` | Not needed in 3.13 |
| `Optional[X]` | `X \| None` |
| `Union[X, Y]` | `X \| Y` |
| `Any` as a lazy escape hatch | `Protocol`, `TypedDict`, or generic |
| `import requests` | `import httpx` |
| `urllib.request` for HTTP | `httpx.AsyncClient` |
| `pip install` / `pip freeze` | `uv add` / `uv export` |
| `poetry add` / `poetry install` | `uv add` / `uv sync` |
| `python -m venv` | `uv venv` or just `uv run` |
| `black`, `isort`, `flake8`, `pylint` | `ruff format`, `ruff check` |
| `mypy` (new projects) | `ty check` |
| `os.path.join(...)` | `Path(...) / ...` |
| `open("file")` | `Path("file").read_text()` |
| `asyncio.gather` for fail-fast concurrency | `asyncio.TaskGroup` |
| `time.sleep` in retry loops | `tenacity` decorators |
| `subprocess.call` / `os.system` | `subprocess.run(..., check=True)` |
| `subprocess.run(..., shell=True)` | Pass a list, never a shell string |
| `logging.basicConfig(...)` | `structlog` or `loguru` |
| `python-dotenv` / manual `os.environ` | `pydantic-settings` `BaseSettings` |
| `setup.py` / `requirements.txt` | `pyproject.toml` + `uv` |
| `assert` for runtime validation | `raise ValueError`/`TypeError` explicitly |
| `raise X` inside `except` | `raise X from exc` — preserve chain |
| `"hello %s" % name` / `"{}".format(name)` | `f"hello {name}"` |
| Mutable class-level `items: list = []` | `field(default_factory=list)` in dataclass |
| Mutable default args `def f(x=[])` | `x: list \| None = None` sentinel |
| Bare `except:` | `except SomeError:` always |
| `except Exception: pass` | At minimum log and re-raise |
| `if x == None` / `if x == True` | `if x is None` / `if x` |


## Type Annotations

### Never import legacy typing generics

```python
# ❌ banned
from typing import List, Dict, Set, Tuple, FrozenSet, Type
from typing import Optional, Union

def process(items: List[str]) -> Dict[str, int]: ...
def find(val: Optional[str]) -> Optional[str]: ...
def merge(a: Union[str, int]) -> Union[str, int]: ...

# ✅ correct
def process(items: list[str]) -> dict[str, int]: ...
def find(val: str | None) -> str | None: ...
def merge(a: str | int) -> str | int: ...
```

### Never use old-style TypeVar

```python
# ❌ banned
from typing import TypeVar
T = TypeVar("T")
def first(items: list[T]) -> T: ...

# ✅ correct — PEP 695 (3.12+)
def first[T](items: list[T]) -> T: ...

class Stack[T]:
    def __init__(self) -> None:
        self._items: list[T] = []
```

### Never use `from __future__ import annotations` — this is a hard ban in Python 3.13+

**STOP.** If you see `from __future__ import annotations` in code you are about to write or edit,
*remove it immediately*. It is a 3.7-era workaround for forward references that is **never needed**
in Python 3.13+ and actively causes bugs — code that calls `get_type_hints()` at runtime will
behave incorrectly. There is no exception.

```python
# ❌ banned — remove this immediately if you see it
from __future__ import annotations

# ✅ just write the annotation directly — no string quoting needed, ever
class Node:
    def __init__(self, next: Node | None = None) -> None:
        self.next = next
# Or with a type alias (PEP 695 — expression, not string):
type NodeRef = Node | None
```

### Never use `Any` as a lazy escape hatch

```python
# ❌ lazy
from typing import Any
def process(data: Any) -> Any: ...

# ✅ use a Protocol, TypedDict, or generic instead
from typing import Protocol
class Processable(Protocol):
    def process(self) -> dict[str, str]: ...
```

### Always annotate return types

```python
# ❌ missing return type — ty/mypy will warn; also hard to reason about
def build_config(path: str):
    ...

# ✅
def build_config(path: str) -> Config:
    ...
```


## Package Choices

### HTTP — never use `requests` or `urllib`

```python
# ❌ banned
import requests
resp = requests.get("https://example.com")

import urllib.request
with urllib.request.urlopen("https://example.com") as r:
    ...

# ✅ httpx with async
import httpx

async def fetch(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
```

### CLI — prefer `cyclopts` or `typer` over raw `argparse`/`click`

**argparse is the default Python stdlib choice — it is always the wrong answer for new code.**
Its stringly-typed API, manual `add_argument` chaining, and lack of type coercion make it verbose
and error-prone. Always reach for cyclopts or typer.

**Minimal cyclopts template** — use this directly for any CLI that needs arguments:

```python
# ✅ cyclopts — type-driven, zero boilerplate, type-safe
import cyclopts

app = cyclopts.App()

@app.command
def main(name: str, count: int = 1) -> None:
    """Print a greeting."""
    for _ in range(count):
        print(f"Hello, {name}!")

app()
```

```python
# ❌ argparse — verbose, stringly-typed, no type coercion
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--name", type=str, required=True)
parser.add_argument("--count", type=int, default=1)
args = parser.parse_args()
```

If cyclopts is unavailable, typer is the next best choice. Never write raw argparse for new code.

### Config / env — never use `python-dotenv` + raw `os.environ`

```python
# ❌ manual, no validation, no type safety
import os
from dotenv import load_dotenv
load_dotenv()
db_url = os.environ["DATABASE_URL"]  # KeyError if missing, no type

# ✅ pydantic-settings — validated, typed, .env-aware
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    debug: bool = False
    max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="forbid",  # <--- always use this; rejects unexpected env vars at startup
    )

settings = Settings()
```

**`extra="forbid"` is the only correct default for settings classes.**
It raises `ValidationError` if the environment contains env var names not declared in the class,
catching typos immediately. `extra="ignore"` silently swallows typos — it is always wrong.
Do not add `@field_validator` on top of `Field(...)` constraints for the same attribute — pick one.

### Logging — never use `logging.basicConfig`

```python
# ❌ unstructured, hard to parse in prod
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("user %s logged in", user_id)

# ✅ structlog — structured, composable, JSON-ready
import structlog
log = structlog.get_logger()
log.info("user_logged_in", user_id=user_id)
```

### Serialization — never hand-roll JSON models

Don't index raw `dict` responses directly — use Pydantic for validation and type safety.
See the `pydantic-v2` skill for full patterns.

```python
# ❌
data = json.loads(raw)
user_id = data["user"]["id"]  # KeyError waiting to happen

# ✅
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str

user = User.model_validate(data["user"])
```


## Code Style

### Never use mutable default arguments — always use the None sentinel

The mutable default argument bug is one of Python's most insidious classic bugs. Every
call that omits the argument shares the same object — modifications persist across calls.

**The rule: when a parameter is optional and mutable, the default must be `None`.**

```python
# ❌ classic bug — shared across all calls
def append_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# ✅ correct — None sentinel, initialized inside the function
def append_item(item: str, items: list[str] | None = None) -> list[str]:
    result = items if items is not None else []
    result.append(item)
    return result
```

The same applies to dict defaults:

```python
# ❌ shared dict across calls
def add_tag(tags: dict[str, str] = {}) -> dict[str, str]:
    tags["latest"] = "v1"
    return tags

# ✅
def add_tag(tags: dict[str, str] | None = None) -> dict[str, str]:
    result = tags if tags is not None else {}
    result["latest"] = "v1"
    return result
```

### Never use bare `except` or silent `except`

```python
# ❌ swallows everything
try:
    do_thing()
except:
    pass

# ❌ swallows and hides
try:
    do_thing()
except Exception:
    pass

# ✅ specific, logged, re-raised
try:
    do_thing()
except ValueError as exc:
    log.warning("invalid_input", error=str(exc))
    raise
```

### Always chain exceptions with `raise ... from`

```python
# ❌ original traceback lost — confusing in prod
try:
    result = parse(raw)
except json.JSONDecodeError:
    raise ValueError("bad payload")

# ✅ chain preserves full context
try:
    result = parse(raw)
except json.JSONDecodeError as exc:
    raise ValueError("bad payload") from exc
```

### Never use `assert` for runtime validation

`assert` statements are stripped when Python runs with `-O`. Use explicit raises instead.

```python
# ❌ silently disabled in optimized builds
assert user_id > 0, "user_id must be positive"
assert isinstance(data, dict), "expected dict"

# ✅ explicit, always runs
if user_id <= 0:
    raise ValueError(f"user_id must be positive, got {user_id}")
if not isinstance(data, dict):
    raise TypeError(f"expected dict, got {type(data).__name__}")
```

### Never use `%` or `.format()` for string interpolation

```python
# ❌ old-style
msg = "Hello %s, you have %d messages" % (name, count)
msg = "Hello {}, you have {} messages".format(name, count)

# ✅ f-string always
msg = f"Hello {name}, you have {count} messages"
```

### Never use mutable class-level variables

Distinct from mutable default args — this is shared state across *all instances*.

```python
# ❌ all instances share the same list
class TaskQueue:
    tasks: list[str] = []  # class variable, not instance variable

    def add(self, task: str) -> None:
        self.tasks.append(task)  # mutates shared state

# ✅ initialise in __init__ or use dataclass
from dataclasses import dataclass, field

@dataclass
class TaskQueue:
    tasks: list[str] = field(default_factory=list)

    def add(self, task: str) -> None:
        self.tasks.append(task)
```

### Never use `os.path` — use `pathlib`

```python
# ❌
import os
path = os.path.join(base_dir, "config", "settings.toml")
with open(path) as f:
    content = f.read()

# ✅
from pathlib import Path
path = Path(base_dir) / "config" / "settings.toml"
content = path.read_text()
```


## Async Patterns

### Concurrent HTTP fetching — the full pattern

When writing async functions that fetch multiple URLs concurrently, use this exact scaffold:

```python
# ✅ the complete pattern for concurrent HTTP fetching
import anyio
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

@retry(
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=20),
    reraise=True,
)
async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()

async def fetch_all(urls: list[str]) -> list[dict]:
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        async with anyio.create_task_group() as tg:
            async def _fetch(url: str) -> None:
                try:
                    results.append(await _fetch_one(client, url))
                except Exception:
                    pass  # skip failed URLs; results list already captures successes
            for url in urls:
                tg.start_soon(_fetch, url)
    return results
```

Key rules:
- **Never** use `asyncio.gather` as the primary concurrency primitive for HTTP fan-out.
- **Always** use `anyio.create_task_group()` (or `asyncio.TaskGroup`) for structured concurrency.
- **Always** add a `@retry` decorator with `reraise=True` for network calls.
- **Never** use `time.sleep` in retry loops — tenacity handles exponential backoff correctly.
- **Never** use `requests` or `urllib` in async code — always use `httpx.AsyncClient`.


## Tooling

### Never use `pip` directly

```bash
# ❌
pip install httpx
pip freeze > requirements.txt

# ✅
uv add httpx
uv export --format requirements-txt > requirements.txt  # only if needed for deploy
```

### Never use `poetry`, `black`, `isort`, `flake8`, `pylint`, `mypy` in new projects

```bash
# ❌
poetry add httpx
black .
isort .
flake8 .
mypy .

# ✅
uv add httpx
uv run ruff format .
uv run ruff check --fix .
uv run ty check
```

### Never use `setup.py` or bare `requirements.txt` as source of truth

All project metadata, dependencies, and tool config belong in `pyproject.toml`.
`requirements.txt` is only acceptable as a *lockfile export* for deployment, not the source.

### Never use `subprocess.call`, `os.system`, or `shell=True`

```python
# ❌ no error checking, unsafe
os.system("git commit -m 'fix'")
subprocess.call(["git", "commit", "-m", "fix"])

# ❌ shell=True is a command injection vector — never use with untrusted input
subprocess.run(f"git commit -m '{message}'", shell=True, check=True)

# ✅ always pass a list, check=True
import subprocess
subprocess.run(["git", "commit", "-m", message], check=True)

# ✅ async
import asyncio
proc = await asyncio.create_subprocess_exec(
    "git", "commit", "-m", message,
    stdout=asyncio.subprocess.PIPE,
)
await proc.wait()
```


## Imports

### Never import inside functions (except TYPE_CHECKING blocks)

```python
# ❌ hides dependencies, slower repeated calls
def process() -> None:
    import json
    import httpx
    ...

# ✅ always at module top
import json
import httpx

def process() -> None:
    ...

# ✅ TYPE_CHECKING is the only valid exception
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from mymodule import HeavyType
```


## See Also

Cross-reference `python-modern` for the canonical *positive* patterns — what to write once
you've avoided what's listed here.
