from fastapi.testclient import TestClient

from backend.server.app import app


def test_health_and_ready(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("RETRIEVER", "duckduckgo")

    client = TestClient(app)

    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json().get("status") == "ok"

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert "ready" in ready.json()
