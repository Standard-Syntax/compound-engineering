from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    """Centralized configuration for the CE work engine.

    All settings can be overridden via CE_* environment variables.
    """

    model_config = SettingsConfigDict(
        env_prefix="CE_",
        env_file=".env",
        extra="ignore",
    )

    model_name: str = "claude-sonnet-4-20250514"
    max_iterations: int = 5
    tool_call_budget: int = 10
    lint_timeout: float = 30.0
    git_timeout: float = 10.0
    pytest_timeout: float = 120.0
    context_pack_path: Path = Path(".context/compound-engineering/context-pack.md")
    learnings_path: Path = Path(".context/compound-engineering/learnings")
    plan_gaps_path: Path = Path(".context/compound-engineering/plan-gaps.md")


settings = EngineSettings()
