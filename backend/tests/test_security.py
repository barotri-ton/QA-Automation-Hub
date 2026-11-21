from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app


def test_invalid_directory_rejected_when_registration_enabled(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("QA_HUB_ALLOW_LOCAL_PATHS", "true")
    result = TestClient(app).post("/api/repositories", json={
        "name": "missing-directory-test",
        "path": str(tmp_path / "does-not-exist"),
    })
    assert result.status_code == 400


def test_unknown_repository_returns_404():
    result = TestClient(app).get("/api/repositories/999999999/tests")
    assert result.status_code == 404
