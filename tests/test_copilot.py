import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from northstar import copilot
from northstar.api import app
from northstar.db import connection
from northstar.schemas import CaseRequest, CaseReview, ProviderConfig


class DraftProvider:
    async def complete_json(self, system, user):
        assert "human IT analyst" in system
        assert "PROCEDURES" in user
        return {
            "summary": "VPN connected but internal resources are inaccessible.",
            "reply": "Please share the VPN error and the time it occurred. Do not share MFA codes.",
            "suggested_steps": [
                "Confirm general internet access",
                "Record the VPN client error and timestamp",
            ],
            "clarifying_questions": ["Can you reach other internal resources?"],
            "escalation": None,
            "cautions": ["Verify account state through the approved workflow."],
            "procedure_slugs": ["vpn-troubleshooting"],
        }


def case_request():
    return CaseRequest(
        title="VPN portal inaccessible",
        body="VPN connected, internal portal does not load.",
        provider=ProviderConfig(
            provider="openrouter", model="openrouter/free", api_key="demo-secret"
        ),
        procedure_slugs=["vpn-troubleshooting"],
    )


def test_draft_then_human_review_persists(database, monkeypatch):
    monkeypatch.setattr(copilot, "build_provider", lambda config: DraftProvider())
    req = case_request()
    case_id = copilot.create_case(req)
    asyncio.run(copilot.draft_case(req, case_id))
    case = copilot.get_case(case_id)
    assert case["status"] == "ready"
    assert case["reviewed_reply"] is None
    assert case["reviews"] == []
    assert case["sources"][0]["slug"] == "vpn-troubleshooting"
    assert case["checks"]
    with TestClient(app) as client:
        review = client.post(
            f"/api/cases/{case_id}/review",
            json={
                "reply": "My edited reply",
                "notes": "I verified internet access",
                "completed_steps": [0],
            },
        )
        assert review.status_code == 200
        assert review.json()["status"] == "reviewed"
        assert review.json()["reviewed_reply"] == "My edited reply"
        assert json.loads(review.json()["reviews"][0]["completed_steps_json"]) == [0]
        assert client.get("/").status_code == 200
        assert "Support Copilot" in client.get("/").text
        assert client.get("/quality-lab").status_code == 200
    with TestClient(app) as client:
        assert client.get(f"/api/cases/{case_id}").json()["reviewed_reply"] == "My edited reply"
    with connection() as conn:
        assert "demo-secret" not in "\n".join(conn.iterdump())


def test_review_requires_finished_draft(database):
    case_id = copilot.create_case(case_request())
    with pytest.raises(ValueError):
        copilot.save_review(case_id, CaseReview(reply="Not ready"))


def test_unknown_source_is_rejected(database, monkeypatch):
    class BadSource(DraftProvider):
        async def complete_json(self, system, user):
            result = await super().complete_json(system, user)
            result["procedure_slugs"] = ["invented-policy"]
            return result

    monkeypatch.setattr(copilot, "build_provider", lambda config: BadSource())
    req = case_request()
    case_id = copilot.create_case(req)
    asyncio.run(copilot.draft_case(req, case_id))
    assert copilot.get_case(case_id)["status"] == "failed"


def test_create_case_endpoint_and_procedure_library(database, monkeypatch):
    monkeypatch.setattr(copilot, "build_provider", lambda config: DraftProvider())
    with TestClient(app) as client:
        request = case_request().model_dump(mode="json", exclude={"provider"})
        request["provider"] = {"provider": "openrouter", "model": "openrouter/free"}
        created = client.post("/api/cases", json=request)
        assert created.status_code == 202
        case_id = created.json()["case_id"]
        assert client.get(f"/api/cases/{case_id}").status_code == 200
        assert client.get("/api/cases").json()[0]["id"] == case_id
        assert "VPN" in client.get("/api/procedures/vpn-troubleshooting").json()["content"]
        assert client.get("/api/procedures/unknown").status_code == 404
