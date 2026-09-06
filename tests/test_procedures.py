from pathlib import Path

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
