"""Offline repository checks with an actual HTTP server and isolated SQLite data."""

import json
import os
import py_compile
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import uvicorn

    from northstar.api import app
    from northstar.config import settings

    for path in (ROOT / "northstar").rglob("*.py"):
        py_compile.compile(str(path), doraise=True)
    with tempfile.TemporaryDirectory(prefix="northstar-check-") as temporary:
        env = os.environ.copy()
        env["NORTHSTAR_DB_PATH"] = str(Path(temporary) / "check.db")
        env["NORTHSTAR_PROCEDURES_DIR"] = str(ROOT / "procedures")
        env.pop("NORTHSTAR_API_KEY", None)
        for args in (["--help"], ["sync-procedures"]):
            subprocess.run(
                [sys.executable, "-m", "northstar.cli", *args],
                cwd=ROOT,
                env=env,
                check=True,
                capture_output=True,
            )
        original_db, original_procedures = settings.db_path, settings.procedures_dir
        settings.db_path = Path(env["NORTHSTAR_DB_PATH"])
        settings.procedures_dir = ROOT / "procedures"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            origin = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen(origin + "/api/health", timeout=1) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.2)
            else:
                raise RuntimeError("API did not become healthy within 30 seconds")
            with urllib.request.urlopen(origin + "/api/procedures", timeout=5) as response:
                assert len(json.load(response)) == 7
            for path in ("/", "/quality-lab"):
                with urllib.request.urlopen(origin + path, timeout=5) as response:
                    assert b"Northstar" in response.read()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            settings.db_path, settings.procedures_dir = original_db, original_procedures
            if thread.is_alive():
                raise RuntimeError("HTTP server did not shut down")
    subprocess.run([sys.executable, "-m", "pytest"], cwd=ROOT, check=True)
    print("OK: compilation, CLI, procedures, SQLite, real HTTP startup/health/dashboard, and tests")


if __name__ == "__main__":
    main()
