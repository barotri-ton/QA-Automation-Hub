"""Offline investigation bundle contract checks (no real Jira or VM)."""
from fastapi import HTTPException
from app import investigations


def test_bundle_without_jira(monkeypatch):
    monkeypatch.setattr(investigations, "_repo", lambda _: "/safe")
    monkeypatch.setattr(investigations, "analyze", lambda root, run: {
        "cases": [{"key": "NJM-123", "status": "FAILED", "reason": "Expected 200, got 500"}]
    })
    result = investigations.investigate(1, "run-1", "NJM-123", test_run_id=None, include_jira=False)
    assert result["classification"] == "INCONCLUSIVE"
    assert result["specification"]["state"] == "NOT_CONNECTED"
    assert result["jira_test"] is None
    assert result["jira_published"] is False


def test_missing_case(monkeypatch):
    monkeypatch.setattr(investigations, "_repo", lambda _: "/safe")
    monkeypatch.setattr(investigations, "analyze", lambda root, run: {"cases": []})
    try:
        investigations.investigate(1, "run-1", "NJM-123", test_run_id=None, include_jira=False)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Missing case must return 404")


def test_jira_unavailable_keeps_local_evidence(monkeypatch):
    monkeypatch.setattr(investigations, "_repo", lambda _: "/safe")
    monkeypatch.setattr(investigations, "analyze", lambda root, run: {
        "cases": [{"key": "NJM-123", "status": "BROKEN"}]
    })
    def offline(_):
        raise HTTPException(503, "Jira unavailable")
    monkeypatch.setattr(investigations.jira_api, "test_details", offline)
    result = investigations.investigate(1, "run-1", "NJM-123", test_run_id=None, include_jira=True)
    assert result["runner_evidence"]["status"] == "BROKEN"
    assert result["jira_error"]["status"] == 503
