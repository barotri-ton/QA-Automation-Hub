"""Offline contract tests; no connection to company Jira."""
import httpx
from fastapi.testclient import TestClient

from app.main import app


def test_jira_requires_backend_pat(monkeypatch):
    monkeypatch.delenv("QA_HUB_JIRA_PAT", raising=False)
    response = TestClient(app).get("/api/jira/plans/NJM-182768/snapshot")
    assert response.status_code == 503


def test_jira_invalid_key_rejected_without_network(monkeypatch):
    monkeypatch.setenv("QA_HUB_JIRA_PAT", "fake")
    response = TestClient(app).get("/api/jira/plans/INVALID/snapshot")
    assert response.status_code == 422


def test_jira_plan_preserves_execution_scoped_runs(monkeypatch):
    monkeypatch.setenv("QA_HUB_JIRA_PAT", "fake")
    from app import jira_api
    def fake_get(client, path, params=None):
        if path.endswith("/issue/NJM-182768"):
            return {"fields": {"summary": "Plan", "issuetype": {"name": "Test Plan"}}}
        if path.endswith("/testexecution"):
            return [{"key": "NJM-10"}, {"key": "NJM-20"}]
        if path.endswith("/testexec/NJM-10/test"):
            return [{"key": "NJM-99", "id": 101, "status": "PASS"}]
        if path.endswith("/testexec/NJM-20/test"):
            return [{"key": "NJM-99", "id": 202, "status": "FAIL"}]
        raise AssertionError(path)
    monkeypatch.setattr(jira_api, "_get", fake_get)
    response = TestClient(app).get("/api/jira/plans/NJM-182768/snapshot")
    assert response.status_code == 200
    executions = response.json()["executions"]
    assert executions[0]["cases"][0]["test_run_id"] == 101
    assert executions[1]["cases"][0]["test_run_id"] == 202
