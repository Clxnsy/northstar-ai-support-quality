from pathlib import Path

import pytest

from northstar.config import settings
from northstar.db import init_db
from northstar.procedures import sync_to_db


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", tmp_path / "test.db")
    monkeypatch.setattr(
        settings, "procedures_dir", Path(__file__).resolve().parents[1] / "procedures"
    )
    monkeypatch.setattr(settings, "api_key", None)
    init_db()
    sync_to_db()
    return settings.db_path
