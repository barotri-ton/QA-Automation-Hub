from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
PLAN = {
    "jira_key": "NJM-1000",
    "executions": [
        {"jira_key": "NJM-1100", "cases": [
            {"jira_key": "NJM-101"}, {"jira_key": "NJM-102"}]},
        {"jira_key": "NJM-1200", "cases": [
            {"jira_key": "NJM-101"}]},
    ],
    "mappings": {"NJM-101": "test_login.py::test_login"},
}


def test_review_endpoint():
    result = client.post("/api/xray/preview/review", json=PLAN)
    assert result.status_code == 200
    assert len(result.json()["executions"]) == 2


def test_suite_preview_groups_sequentially():
    result = client.post("/api/xray/preview/suite", json={
        **PLAN,
        "selected": {
            "NJM-1100": ["NJM-101", "NJM-102"],
            "NJM-1200": ["NJM-101"],
        },
    })
    assert result.status_code == 200
    body = result.json()
    assert body["preview_only"] is True
    assert body["mode"] == "SEQUENTIAL"
    assert body["run"]["total"] == 2
    assert body["run"]["missing_automation"] == 1
    assert [g["execution_key"] for g in body["run"]["groups"]] == [
        "NJM-1100", "NJM-1200"
    ]


def test_unknown_selected_case_rejected():
    result = client.post("/api/xray/preview/suite", json={
        **PLAN, "selected": {"NJM-1100": ["NJM-999"]},
    })
    assert result.status_code == 422
