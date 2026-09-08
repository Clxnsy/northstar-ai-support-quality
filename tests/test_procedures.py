from pathlib import Path

import pytest

from northstar import db
from northstar.config import settings
from northstar.procedures import load_all, sync_to_db


def test_procedure_files_are_valid():
    procedures = load_all(Path("procedures"))
    assert len(procedures) >= 6
    assert len({p.slug for p in procedures}) == len(procedures)
    assert all(p.required_steps for p in procedures)


def test_database_initializes_and_syncs(tmp_path, monkeypatch):
    test_db = tmp_path / "northstar.db"
    monkeypatch.setattr(settings, "db_path", test_db)
    monkeypatch.setattr(settings, "procedures_dir", Path("procedures"))
    db.init_db()
    count = sync_to_db()
    assert count >= 6
    with db.connection() as conn:
        stored = conn.execute("SELECT COUNT(*) FROM procedures").fetchone()[0]
        assert stored == count


def test_search_and_deleted_procedures_are_synced(database, tmp_path):
    from northstar.procedures import retrieve

    assert any(p.slug == "vpn-troubleshooting" for p in retrieve("VPN tunnel connection", limit=3))
    content = Path("procedures/vpn.md").read_text()
    (tmp_path / "vpn.md").write_text(content)
    assert sync_to_db(tmp_path) == 1
    assert len(db.query_all("SELECT slug FROM procedures")) == 1


def test_invalid_metadata_rejected(tmp_path):
    content = Path("procedures/vpn.md").read_text()
    (tmp_path / "bad.md").write_text(content.replace("severity: P3", "severity: P9"))
    with pytest.raises(ValueError, match="severity"):
        load_all(tmp_path)


def test_duplicate_slugs_rejected(tmp_path):
    content = Path("procedures/vpn.md").read_text()
    (tmp_path / "one.md").write_text(content)
    (tmp_path / "two.md").write_text(content)
    with pytest.raises(ValueError, match="unique"):
        load_all(tmp_path)
