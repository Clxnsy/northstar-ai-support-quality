from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NORTHSTAR_", env_file=".env", extra="ignore")

    db_path: Path = Path("./data/northstar.db")
    procedures_dir: Path = Path("./procedures")
    default_provider: str = "openai_compatible"
    default_base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4.1-mini"
    api_key: str | None = None
    request_timeout_seconds: int = 90
    max_concurrency: int = 4


settings = Settings()
