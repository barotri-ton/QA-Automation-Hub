from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_runner_disabled_by_default(monkeypatch):
    monkeypatch.delenv("QA_HUB_ENABLE_RUNNER", raising=False)
    result = client.post(
        "/api/runs/does-not-exist/start",
        json={"repository_id": 1},
    )
    assert result.status_code == 403
    assert "disabled" in result.json()["detail"].lower()


def test_runner_status_endpoint():
    response = client.get("/api/runner/status")
    assert response.status_code == 200
    assert "active_run_id" in response.json()


def test_run_progress_not_found():
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404
