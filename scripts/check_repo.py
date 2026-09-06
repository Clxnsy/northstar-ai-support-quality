"""Offline repository validation that does not call an LLM provider."""
from pathlib import Path
import py_compile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from northstar.config import settings
from northstar.db import init_db
from northstar.procedures import load_all, sync_to_db


def main():
    for path in Path("northstar").glob("*.py"):
        py_compile.compile(str(path), doraise=True)
    procedures = load_all(Path("procedures"))
    init_db()
    synced = sync_to_db()
    assert synced == len(procedures)
    print(f"OK: compiled Python and validated/synced {synced} procedures to {settings.db_path}")


if __name__ == "__main__":
    main()
