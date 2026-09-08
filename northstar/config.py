from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NORTHSTAR_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/northstar.db")
    procedures_dir: Path = Path("./procedures")
    default_provider: str = "openai_compatible"
    default_base_url: str = "https://api.openai.com/v1"
    default_model: str = ""
    api_key: str | None = None
    request_timeout_seconds: int = Field(default=90, ge=1, le=600)
    max_concurrency: int = Field(default=4, ge=1, le=12)


settings = Settings()
