name: pydantic-v2
description: >
  Write idiomatic Pydantic v2 Python code using BaseModel, Pydantic dataclasses,
  BaseSettings, Field, validators, model_validator, and serialization patterns.
  Use this skill whenever the user is working with data models, config objects,
  settings management, validation logic, or serialization in Python — even if
  they just say "define a model", "validate this input", "parse this config",
  "load settings from env", or "serialize to JSON". Always use this skill for
  any Python task that involves structured data, not just tasks that explicitly
  mention Pydantic.

# Pydantic v2 — Models, Validation, Settings & Serialization

All code targets **Pydantic v2** with **Python 3.13+** syntax. Never use Pydantic v1
patterns (`@validator`, `class Config`, `orm_mode`, etc.).


## Installation

```toml
# pyproject.toml
dependencies = [
    "pydantic>=2.0",
    "pydantic-settings>=2.0",  # if using BaseSettings
]
```

```bash
uv add pydantic
uv add pydantic-settings  # for settings management
```


## BaseModel Patterns

### Basic model

```python
from pydantic import BaseModel, Field

class User(BaseModel):
    id: int
    name: str
    email: str
    age: int | None = None
```

### Strict mode

Use `model_config` (never `class Config`):

```python
from pydantic import BaseModel, ConfigDict

class StrictUser(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    id: int
    name: str
```

`frozen=True` makes instances hashable and immutable (like `dataclass(frozen=True)`).
`strict=True` disables coercion — `"1"` will not parse as `int`.

### Common ConfigDict options

```python
from pydantic import ConfigDict

model_config = ConfigDict(
    strict=False,          # allow coercion (default)
    frozen=False,          # allow mutation (default)
    populate_by_name=True, # allow field name OR alias
    extra="forbid",        # reject unknown fields
    extra="ignore",        # silently drop unknown fields (default)
    str_strip_whitespace=True,
)
```


## Field

```python
from pydantic import BaseModel, Field

class Product(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0, description="Price in USD")
    sku: str = Field(pattern=r"^[A-Z]{2}-\d{4}$")
    tags: list[str] = Field(default_factory=list)

    # Alias: parse from "product_name" in input, expose as "name"
    display_name: str = Field(alias="product_name")
```

### Field constraints cheatsheet

| Constraint | Types | Meaning |
|---|---|---|
| `gt`, `ge`, `lt`, `le` | numeric | greater/less than (exclusive/inclusive) |
| `min_length`, `max_length` | str, list | length bounds |
| `pattern` | str | regex match |
| `default_factory` | any | callable for mutable defaults |
| `alias` | any | input key name |
| `serialization_alias` | any | output key name (for `model_dump`) |
| `exclude` | any | omit from serialization |
| `repr` | any | include in `__repr__` |


## Validators

### `@field_validator` (replaces v1 `@validator`)

```python
from pydantic import BaseModel, field_validator

class User(BaseModel):
    name: str
    email: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()
```

Validate multiple fields together with `mode="before"` (runs on raw input before type coercion):

```python
    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v
```

### `@model_validator` (cross-field validation)

```python
from pydantic import BaseModel, model_validator
from typing import Self

class DateRange(BaseModel):
    start: int
    end: int

    @model_validator(mode="after")
    def check_range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self
```

`mode="after"` receives the fully-constructed model instance.
`mode="before"` receives the raw input dict — useful for remapping keys or coercing structure before field parsing.

```python
    @model_validator(mode="before")
    @classmethod
    def remap_legacy_keys(cls, data: dict) -> dict:
        if "user_name" in data:
            data["name"] = data.pop("user_name")
        return data
```


## Pydantic Dataclasses

Use when you want a Pydantic-validated dataclass that still behaves like a stdlib dataclass
at runtime (e.g., for libraries that inspect `__dataclass_fields__`).

```python
from pydantic.dataclasses import dataclass
from pydantic import Field, ConfigDict

@dataclass(config=ConfigDict(frozen=True, strict=True))
class Point:
    x: float
    y: float
    label: str = Field(default="", max_length=50)
```

Pydantic dataclasses support `Field`, `field_validator`, and `model_validator` just like
`BaseModel`. They do **not** support `model_dump` / `model_dump_json` directly — use
`pydantic.dataclasses.dataclass` instances via `TypeAdapter` for serialization:

```python
from pydantic import TypeAdapter

ta = TypeAdapter(Point)
d = ta.dump_python(point)         # → dict
j = ta.dump_json(point)           # → bytes
p = ta.validate_python({"x": 1.0, "y": 2.0})
```


## Serialization

### `model_dump` and `model_dump_json`

```python
user = User(id=1, name="Alice", email="alice@example.com")

# to dict
user.model_dump()
user.model_dump(exclude_none=True)       # omit None fields
user.model_dump(exclude={"email"})       # omit specific fields
user.model_dump(include={"id", "name"})  # only these fields
user.model_dump(by_alias=True)           # use Field(alias=...) as keys

# to JSON bytes
user.model_dump_json()
user.model_dump_json(exclude_none=True)
```

### Custom serializers — `@field_serializer`

```python
from pydantic import BaseModel, field_serializer
from datetime import datetime

class Event(BaseModel):
    name: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, v: datetime) -> str:
        return v.isoformat()
```

### Custom serializers — `@model_serializer`

```python
from pydantic import BaseModel, model_serializer

class Token(BaseModel):
    access: str
    refresh: str

    @model_serializer
    def serialize(self) -> dict[str, str]:
        return {"token": self.access}  # custom shape on dump
```

### Serialization aliases

To use different keys in output vs input:

```python
class Response(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(serialization_alias="userId")
    full_name: str = Field(serialization_alias="fullName")

resp = Response(user_id=1, full_name="Alice")
resp.model_dump(by_alias=True)  # → {"userId": 1, "fullName": "Alice"}
```


## BaseSettings (pydantic-settings)

### Basic settings with env vars

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",          # APP_DATABASE_URL, APP_DEBUG, etc.
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    debug: bool = False
    port: int = 8080
```

```python
# Instantiate — reads from env + .env file automatically
settings = Settings()
```

### Multiple sources: env + .env + TOML + secrets

```python
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    SecretsSettingsSource,
    PydanticBaseSettingsSource,
)
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        toml_file="config.toml",
        secrets_dir="/run/secrets",
        extra="ignore",
    )

    database_url: str
    api_key: str
    debug: bool = False
    port: int = 8080

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: init > env > .env > TOML > secrets
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
```

**Source priority** (first wins): `init_settings` → `env_settings` → `dotenv_settings` →
`TomlConfigSettingsSource` → `file_secret_settings`.

### Nested settings

```python
class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str

class Settings(BaseSettings):
    db: DatabaseSettings
    debug: bool = False
```

With env vars, use double-underscore for nesting: `APP_DB__HOST=myhost`.


## Patterns to Avoid

| ❌ Pydantic v1 | ✅ Pydantic v2 |
|---|---|
| `@validator("field")` | `@field_validator("field")` |
| `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
| `class Config: allow_mutation = False` | `ConfigDict(frozen=True)` |
| `class Config: schema_extra = {...}` | `ConfigDict(json_schema_extra={...})` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `.parse_obj(data)` | `Model.model_validate(data)` |
| `.parse_raw(json_str)` | `Model.model_validate_json(json_str)` |
| `from pydantic import validator` | `from pydantic import field_validator` |
| `__fields__` | `model_fields` |
