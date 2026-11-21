from fastapi.testclient import TestClient
from app.main import app

def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_local_path_registration_disabled_by_default(monkeypatch):
    monkeypatch.delenv("QA_HUB_ALLOW_LOCAL_PATHS", raising=False)
    response = TestClient(app).post("/api/repositories", json={"name": "demo", "path": "."})
    assert response.status_code == 403
