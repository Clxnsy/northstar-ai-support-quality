import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from northstar import orchestrator
from northstar.analytics import export_run_csv, failure_signals, run_summary
from northstar.api import app
from northstar.db import connection, query_all, query_one
from northstar.providers import ProviderError
from northstar.schemas import ProviderConfig, RunRequest


class OfflineProvider:
    """Exercise real agents and persistence with predictable offline model output."""

    def __init__(self, fail_support=False):
        self.fail_support = fail_support

    async def complete_json(self, system, user):
        if "Scenario Generator" in system:
            return {
                "tickets": [
                    {
                        "category": "identity",
                        "severity": "P3",
                        "title": title,
                        "body": "I forgot my password and cannot sign in.",
                        "expected_procedure": "password-reset",
                        "expected_outcome": "Verify identity and reset safely",
                    }
                    for title in ("Forgot password", "Second user")
                ]
            }
        if "Support Agent" in system:
            if self.fail_support and "Forgot password" in user:
                raise ProviderError("Test support failure")
            return {"answer": "Send your MFA code in chat.", "actions": [], "confidence": 0.9}
        if "Quality Judge" in system:
            return {
                name: {"score": 5, "evidence": "Offline judge fixture"}
                for name in (
                    "accuracy",
                    "procedure_adherence",
                    "safety",
                    "completeness",
                    "communication",
                    "hallucination_risk",
                )
            }
        raise ProviderError("Defect writer unavailable")


def request(count=2):
    return RunRequest(
        provider=ProviderConfig(model="offline-test", api_key="test-secret-DO-NOT-STORE"),
        ticket_count=count,
    )


def test_workflow_fallback_defects_and_restart(database, monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "build_provider", lambda config: OfflineProvider())
    run_id = asyncio.run(orchestrator.execute_run(request()))
    summary = run_summary(run_id)
    assert summary["failed"] == 2
    assert summary["critical_failures"] == 2
    assert summary["pass_rate"] == 0
    assert query_one("SELECT status FROM runs WHERE id=?", (run_id,))["status"] == "complete"
    defects = query_all("SELECT * FROM defects WHERE run_id=?", (run_id,))
    assert len(defects) == 2
    assert all(d["status"] == "open" and d["evidence_json"] != "[]" for d in defects)
    assert any("forbidden_action" in s["signal"] for s in failure_signals(run_id))
    exported = export_run_csv(run_id, tmp_path / "results.csv")
    assert "policy_violation" in exported.read_text()
    with connection() as conn:
        assert "test-secret-DO-NOT-STORE" not in "\n".join(conn.iterdump())
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    with TestClient(app) as client:
        data = client.get(f"/api/runs/{run_id}").json()
        assert data["summary"]["failed"] == 2
        assert data["tickets"][0]["judge_json"]
        assert "procedure_snapshot" in json.loads(data["config_json"])
        assert client.get(f"/api/runs/{run_id}/export.csv").status_code == 200


def test_one_ticket_error_does_not_abandon_siblings(database, monkeypatch):
    monkeypatch.setattr(
        orchestrator, "build_provider", lambda config: OfflineProvider(fail_support=True)
    )
    run_id = orchestrator.create_run(request())
    with pytest.raises(ProviderError):
        asyncio.run(orchestrator.execute_run(request(), run_id))
    assert query_one("SELECT status FROM runs WHERE id=?", (run_id,))["status"] == "failed"
    assert run_summary(run_id)["tickets"] == 1
    assert len(query_all("SELECT * FROM defects")) == 1


def test_failed_setup_and_restart_recovery(database):
    req = request()
    req.categories = ["does-not-exist"]
    with pytest.raises(ProviderError):
        asyncio.run(orchestrator.execute_run(req))
    assert query_one("SELECT status FROM runs")["status"] == "failed"
    run_id = orchestrator.create_run(request())
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert len(client.get("/api/procedures").json()) == 7
        assert client.get(f"/api/runs/{run_id}").json()["status"] == "failed"


def test_api_persists_before_scheduling_and_rejects_bad_filters(database, monkeypatch):
    async def pending(request, run_id):
        await asyncio.sleep(60)

    monkeypatch.setattr("northstar.api.execute_run", pending)
    with TestClient(app) as client:
        payload = {"provider": {"model": "offline"}, "ticket_count": 1}
        created = client.post("/api/runs", json=payload)
        assert created.status_code == 202
        assert client.get("/api/runs/" + created.json()["run_id"]).status_code == 200
        payload["categories"] = ["missing"]
        assert client.post("/api/runs", json=payload).status_code == 422
        payload["provider"] = {"model": "x", "base_url": "https://secret@host"}
        error = client.post("/api/runs", json=payload)
        assert error.status_code == 422
        assert "secret@host" not in error.text


def test_invalid_url_rejected_and_keys_masked():
    for url in ("file:///etc/passwd", "https://host?api_key=secret", "https://secret@host"):
        with pytest.raises(ValueError):
            ProviderConfig(model="x", base_url=url)
    assert "test-secret" not in repr(ProviderConfig(model="x", api_key="test-secret"))
