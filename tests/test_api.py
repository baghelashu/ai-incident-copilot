import pytest
from fastapi.testclient import TestClient

from copilot import api
from copilot.agent import IncidentCopilot


@pytest.fixture
def client(settings, monkeypatch):
    monkeypatch.setattr(api, "_copilot", IncidentCopilot(settings))
    return TestClient(api.app)


def test_upload_then_ask(client, order_log):
    upload = client.post("/logs/upload", files={"file": ("order-service.log", order_log, "text/plain")})
    assert upload.status_code == 200
    body = upload.json()
    assert body["anomalies"] and body["clusters"]

    answer = client.post("/ask", json={"session_id": body["session_id"], "question": "root cause?"})
    assert answer.status_code == 200
    assert "### Recommended fix" in answer.json()["report"]


def test_ask_requires_logs(client):
    assert client.post("/ask", json={"question": "x"}).status_code == 404


def test_knowledge_search(client):
    hits = client.get("/knowledge/search", params={"q": "S0C7 abend packed decimal"}).json()
    assert "mainframe-batch-abend" in hits[0]["source"] or "s0c7" in hits[0]["source"]
