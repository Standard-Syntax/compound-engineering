name: httpx-async
description: >
  Write modern Python 3.13 async HTTP code using httpx, tenacity, anyio, and structured
  Result types. Use this skill whenever the user is making HTTP requests, building API
  clients, writing async networking code, adding retry logic, handling HTTP errors, or
  structuring concurrent async tasks. Trigger on any mention of: httpx, tenacity, anyio,
  async HTTP, retries, API client, AsyncClient, cancel scope, task group, Result type,
  Ok/Err pattern, structured concurrency, SSE, server-sent events, streaming responses,
  multipart upload, file upload, or cookie jar. Always use this skill instead of requests,
  aiohttp, urllib3, or raw asyncio patterns.

# httpx / tenacity / anyio — Modern Async HTTP for Python 3.13

Complements `python-modern` (toolchain, type syntax) and `pydantic-v2` (response models).
This skill covers: httpx AsyncClient patterns, tenacity retry strategies, anyio structured
concurrency, httpx error hierarchy, a stdlib-only Result type, SSE/streaming responses,
multipart uploads, and cookie jar management.


## Dependencies

```toml
# pyproject.toml
dependencies = [
    "httpx>=0.27",
    "tenacity>=9.0",
    "anyio>=4.0",
]
```

```bash
uv add httpx tenacity anyio
```

For PEP 723 inline scripts:

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx>=0.27", "tenacity>=9.0", "anyio>=4.0"]
# ///
```


## httpx AsyncClient

### Always use as an async context manager

```python
import httpx

async def main() -> None:
    async with httpx.AsyncClient(
        base_url="https://api.example.com",
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={"Accept": "application/json"},
    ) as client:
        response = await client.get("/users/1")
        response.raise_for_status()
        data = response.json()
```

Never instantiate `AsyncClient` without a context manager — it leaks connections.

### Timeouts

```python
# All-in-one timeout
timeout = httpx.Timeout(10.0)

# Per-phase control (preferred for production)
timeout = httpx.Timeout(
    connect=5.0,    # TCP connect
    read=30.0,      # waiting for first byte
    write=10.0,     # sending request body
    pool=5.0,       # waiting for a pooled connection
)

# Disable entirely (only for local dev/testing)
timeout = httpx.Timeout(None)
```

### Auth

```python
# Bearer token
client = httpx.AsyncClient(
    auth=("", token),                          # basic auth with empty user
    headers={"Authorization": f"Bearer {token}"},  # or explicit header
)

# Custom auth flow via callable
class BearerAuth(httpx.Auth):
    def __init__(self, token: str) -> None:
        self.token = token

    def auth_flow(self, request: httpx.Request) -> httpx.Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request
```

### Response handling

```python
response = await client.get("/items")
response.raise_for_status()          # raises HTTPStatusError on 4xx/5xx

# JSON
data: dict = response.json()

# Text
text: str = response.text

# Bytes
raw: bytes = response.content

# Headers
content_type = response.headers["content-type"]

# Status
assert response.status_code == 200
assert response.is_success              # 2xx
assert response.is_client_error         # 4xx
assert response.is_server_error         # 5xx
```

### Reusable service client pattern

```python
from dataclasses import dataclass
import httpx

@dataclass(slots=True)
class ApiClient:
    base_url: str
    api_key: str
    timeout: float = 10.0
    _client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ApiClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout, connect=5.0),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ApiClient must be used as async context manager")
        return self._client
```


## tenacity Retry Strategies

### Standard retry decorator

```python
from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_exponential_jitter,
    retry_if_exception_type,
    retry_if_result,
    before_sleep_log,
    RetryError,
)
import logging

logger = logging.getLogger(__name__)

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    response = await client.get(url)
    response.raise_for_status()
    return response
```

### Stop strategies

```python
stop_after_attempt(3)                  # max 3 tries
stop_after_delay(30.0)                 # give up after 30s total
stop_after_attempt(3) | stop_after_delay(30.0)  # whichever first
```

### Wait strategies

```python
wait_exponential(multiplier=1, min=1, max=60)   # 1s, 2s, 4s, ... cap 60s
wait_exponential_jitter(initial=1, max=60)       # exponential + random jitter (preferred)
wait_fixed(2.0)                                  # always wait 2s
wait_random(min=1, max=3)                        # random between 1-3s
wait_exponential(multiplier=0.5) + wait_random(0, 0.5)  # combined
```

### Retry predicates

```python
# On exception type
retry=retry_if_exception_type(httpx.TimeoutException)
retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))

# On HTTP 5xx specifically
def is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500

retry=retry_if_exception(is_retryable)

# On result value
retry=retry_if_result(lambda r: r.status_code == 429)
```

### RetryError + fallback

```python
from tenacity import RetryError

async def fetch_with_fallback(
    client: httpx.AsyncClient,
    url: str,
    fallback: str,
) -> str:
    try:
        response = await fetch(client, url)
        return response.text
    except RetryError:
        logger.error("All retries exhausted for %s, using fallback", url)
        return fallback
    except httpx.HTTPStatusError as e:
        logger.error("HTTP %d from %s", e.response.status_code, url)
        raise
```


## anyio Structured Concurrency

Prefer `anyio` over direct `asyncio` — it's backend-agnostic (asyncio or trio) and has
a cleaner API for cancel scopes and task groups.

```bash
uv add anyio
```

### Task groups (parallel requests)

```python
import anyio
import httpx

async def fetch_all(urls: list[str]) -> list[httpx.Response]:
    results: list[httpx.Response | None] = [None] * len(urls)

    async with httpx.AsyncClient() as client:
        async with anyio.create_task_group() as tg:
            for i, url in enumerate(urls):
                async def _fetch(idx: int = i, u: str = url) -> None:
                    results[idx] = await client.get(u)
                tg.start_soon(_fetch)

    return [r for r in results if r is not None]
```

### Cancel scopes — move_on_after

```python
import anyio

async def fetch_or_skip(client: httpx.AsyncClient, url: str) -> str | None:
    with anyio.move_on_after(5.0) as scope:
        response = await client.get(url)
        return response.text
    if scope.cancelled_caught:
        return None  # timed out, no exception raised
```

### Cancel scopes — fail_after

```python
async def fetch_strict(client: httpx.AsyncClient, url: str) -> str:
    with anyio.fail_after(10.0):  # raises TimeoutError if exceeded
        response = await client.get(url)
        response.raise_for_status()
        return response.text
```

### Entry point — anyio.run

```python
import anyio

async def main() -> None:
    async with httpx.AsyncClient() as client:
        text = await fetch_strict(client, "https://example.com")
        print(text)

if __name__ == "__main__":
    anyio.run(main)   # not asyncio.run — keeps backend-agnostic
```


## httpx Exception Hierarchy

```
httpx.HTTPError
├── httpx.TransportError
│   ├── httpx.TimeoutException
│   │   ├── httpx.ConnectTimeout
│   │   ├── httpx.ReadTimeout
│   │   ├── httpx.WriteTimeout
│   │   └── httpx.PoolTimeout
│   ├── httpx.NetworkError
│   │   ├── httpx.ConnectError
│   │   ├── httpx.ReadError
│   │   └── httpx.WriteError
│   └── httpx.ProxyError
└── httpx.HTTPStatusError     # raised by response.raise_for_status()
```

```python
try:
    response = await client.get(url)
    response.raise_for_status()
except httpx.ConnectTimeout:
    # couldn't establish TCP connection in time
    ...
except httpx.ReadTimeout:
    # connected but server didn't respond in time
    ...
except httpx.NetworkError:
    # DNS failure, connection reset, etc.
    ...
except httpx.HTTPStatusError as e:
    # got a response, but status was 4xx or 5xx
    status = e.response.status_code
    body = e.response.text
    ...
except httpx.HTTPError:
    # catch-all for any httpx error
    ...
```


## Result Type (stdlib, no extra deps)

For callers that want explicit Ok/Err rather than exceptions:

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound=BaseException)

@dataclass(slots=True, frozen=True)
class Ok[T]:
    value: T

@dataclass(slots=True, frozen=True)
class Err[E]:
    error: E

type Result[T, E] = Ok[T] | Err[E]
```

### Usage with httpx

```python
async def safe_fetch(
    client: httpx.AsyncClient,
    url: str,
) -> Result[dict, httpx.HTTPError]:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return Ok(response.json())
    except httpx.HTTPError as e:
        return Err(e)

# Caller — exhaustive match
result = await safe_fetch(client, "https://api.example.com/data")
match result:
    case Ok(value):
        print(value)
    case Err(error):
        print(f"Request failed: {error}")
```

### Combined with tenacity

```python
@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=30),
    reraise=True,
)
async def _fetch_raw(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()

async def fetch_result(
    client: httpx.AsyncClient,
    url: str,
) -> Result[dict, Exception]:
    try:
        return Ok(await _fetch_raw(client, url))
    except (httpx.HTTPError, RetryError) as e:
        return Err(e)
```


## Full Example — Concurrent API Fetches with Retry + Result

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["httpx>=0.27", "tenacity>=9.0", "anyio>=4.0"]
# ///

import anyio
import httpx
from dataclasses import dataclass
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter, RetryError

@dataclass(slots=True, frozen=True)
class Ok[T]:
    value: T

@dataclass(slots=True, frozen=True)
class Err[E]:
    error: E

type Result[T, E] = Ok[T] | Err[E]


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=20),
    reraise=True,
)
async def _get(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url)
    r.raise_for_status()
    return r.json()


async def fetch(client: httpx.AsyncClient, url: str) -> Result[dict, Exception]:
    try:
        return Ok(await _get(client, url))
    except (httpx.HTTPError, RetryError) as e:
        return Err(e)


async def main() -> None:
    urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]
    results: list[Result[dict, Exception]] = [Err(RuntimeError("not started"))] * len(urls)

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        headers={"Accept": "application/json"},
    ) as client:
        async with anyio.create_task_group() as tg:
            for i, url in enumerate(urls):
                async def _run(idx: int = i, u: str = url) -> None:
                    results[idx] = await fetch(client, u)
                tg.start_soon(_run)

    for url, result in zip(urls, results):
        match result:
            case Ok(value):
                print(f"✓ {url}: {value.get('title', '')[:40]}")
            case Err(error):
                print(f"✗ {url}: {error}")


if __name__ == "__main__":
    anyio.run(main)
```


## SSE / Streaming Responses

Use `client.stream()` as an async context manager to avoid buffering the entire response.

### Raw byte streaming

```python
async with client.stream("GET", "/export/large-file") as response:
    response.raise_for_status()
    async for chunk in response.aiter_bytes(chunk_size=65536):
        process(chunk)
```

### Line-by-line streaming (NDJSON, logs)

```python
async with client.stream("GET", "/logs/live") as response:
    response.raise_for_status()
    async for line in response.aiter_lines():
        if line:
            record = json.loads(line)
            handle(record)
```

### Server-Sent Events (SSE)

Install the companion package:

```bash
uv add httpx-sse
```

```python
from httpx_sse import aconnect_sse

async def stream_events(client: httpx.AsyncClient, url: str) -> None:
    async with aconnect_sse(client, "GET", url) as event_source:
        async for event in event_source.aiter_sse():
            print(f"event={event.event!r}  data={event.data!r}  id={event.id!r}")
```

With a POST body (e.g. LLM streaming):

```python
async def stream_completion(
    client: httpx.AsyncClient,
    prompt: str,
) -> AsyncIterator[str]:
    payload = {"prompt": prompt, "stream": True}
    async with aconnect_sse(
        client, "POST", "/completions", json=payload
    ) as event_source:
        async for event in event_source.aiter_sse():
            if event.data == "[DONE]":
                break
            chunk = json.loads(event.data)
            yield chunk["choices"][0]["delta"].get("content", "")
```

Caller:

```python
async for token in stream_completion(client, "Hello"):
    print(token, end="", flush=True)
```

### Timeout note for streaming

Use a long or disabled `read` timeout — the connection can stay open for minutes:

```python
timeout = httpx.Timeout(connect=5.0, read=None, write=10.0, pool=5.0)
```

### SSE error handling

```python
from httpx_sse import SSEError

try:
    async with aconnect_sse(client, "GET", url) as event_source:
        async for event in event_source.aiter_sse():
            ...
except SSEError as e:
    logger.error("SSE protocol error: %s", e)
except httpx.HTTPStatusError as e:
    logger.error("HTTP %d on SSE endpoint", e.response.status_code)
```


## Multipart Uploads

### Single file upload

```python
from pathlib import Path

path = Path("report.pdf")
async with client.stream(
    "POST",
    "/upload",
    files={"file": (path.name, path.open("rb"), "application/pdf")},
) as response:
    response.raise_for_status()
    result = response.json()
```

The `files` tuple is `(filename, file_object, content_type)`. Content-type is optional.

### Multiple files

```python
files = [
    ("attachments", ("photo.jpg", open("photo.jpg", "rb"), "image/jpeg")),
    ("attachments", ("doc.pdf",  open("doc.pdf",  "rb"), "application/pdf")),
]
response = await client.post("/upload/batch", files=files)
response.raise_for_status()
```

### Mixed: files + form fields

```python
response = await client.post(
    "/upload",
    files={"file": ("data.csv", csv_bytes, "text/csv")},
    data={"description": "Monthly report", "tags": "finance,q3"},
)
```

### In-memory bytes (no disk file)

```python
csv_bytes: bytes = generate_csv()
response = await client.post(
    "/ingest",
    files={"upload": ("output.csv", csv_bytes, "text/csv")},
)
```

### Large file streaming upload

Wrap with `client.stream` so the file is not fully buffered in memory:

```python
async def upload_large(client: httpx.AsyncClient, path: Path) -> dict:
    async with client.stream(
        "POST",
        "/upload/large",
        files={"file": (path.name, path.open("rb"), "application/octet-stream")},
        timeout=httpx.Timeout(connect=5.0, read=120.0, write=None, pool=5.0),
    ) as response:
        response.raise_for_status()
        return response.json()
```


## Cookie Jars

### Per-client cookie jar (persists across requests)

```python
client = httpx.AsyncClient(
    base_url="https://example.com",
    cookies={"session": "abc123", "theme": "dark"},
)
# All subsequent requests from this client carry the cookies.
```

### Per-request cookies (one-off override)

```python
response = await client.get("/dashboard", cookies={"override": "value"})
```

### Reading cookies from a response

```python
response = await client.post("/login", json={"user": "alice", "pass": "secret"})
response.raise_for_status()

session_id = response.cookies.get("session_id")
all_cookies: dict[str, str] = dict(response.cookies)
```

### Jar that accumulates cookies across redirects/responses

`httpx.AsyncClient` maintains a `Cookies` jar automatically — responses that set cookies
update it, and the jar is sent on subsequent requests.

```python
async with httpx.AsyncClient(follow_redirects=True) as client:
    await client.post("/login", data={"user": "alice", "pass": "s3cr3t"})
    # session cookie is now in client.cookies
    print(dict(client.cookies))          # {"session_id": "xyz..."}

    profile = await client.get("/me")    # session_id sent automatically
    profile.raise_for_status()
```

### Constructing a `Cookies` object explicitly

```python
jar = httpx.Cookies()
jar.set("session_id", "xyz", domain="example.com", path="/api")
jar.set("csrf",       "tok", domain="example.com")

client = httpx.AsyncClient(cookies=jar)
```

### Exporting / importing cookies (e.g. for persistence)

```python
# Export
serialized: dict[str, str] = dict(client.cookies)

# Import into a new client
new_client = httpx.AsyncClient(cookies=serialized)
```


## What to Avoid

| ❌ Avoid | ✅ Use instead |
|---|---|
| `import requests` | `httpx.AsyncClient` |
| `import aiohttp` | `httpx.AsyncClient` |
| `asyncio.sleep` in retry loops | `tenacity` decorators |
| `asyncio.gather` | `anyio.create_task_group()` |
| `asyncio.wait_for` | `anyio.fail_after()` |
| `asyncio.run(main())` | `anyio.run(main)` |
| `httpx.Client` (sync) | `httpx.AsyncClient` unless explicitly sync needed |
| Bare `except Exception` on HTTP calls | Structured `httpx.HTTPError` / `RetryError` |
| `raise_for_status()` after every line | Call once after `.get`/`.post` etc. |
| `AsyncClient()` without context manager | Always `async with httpx.AsyncClient()` |
| Manual SSE line parsing | `httpx-sse` + `aconnect_sse` |
| `response.content` for large downloads | `client.stream()` + `aiter_bytes()` |
| `open(path).read()` then upload bytes | Pass file object directly to `files=` |
| Manual `Cookie:` header string | `cookies=` param on client or request |
