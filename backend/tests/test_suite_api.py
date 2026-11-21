from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PLAN = {
    "jira_key": "NJM-1000",
    "executions": [
        {
            "jira_key": "NJM-1100",
            "cases": [{"jira_key": "NJM-101"}, {"jira_key": "NJM-102"}],
        },
        {
            "jira_key": "NJM-1200",
            "cases": [{"jira_key": "NJM-101"}],
        },
    ],
    "mappings": {"NJM-101": "test_login.py::test_login"},
    "selected": {
        "NJM-1100": ["NJM-101", "NJM-102"],
        "NJM-1200": ["NJM-101"],
    },
}


def test_save_suite_and_run_persists_grouping():
    response = client.post("/api/suites", json=PLAN)
    assert response.status_code == 201, response.text
    suite_id = response.json()["suite_id"]

    run_response = client.post(f"/api/suites/{suite_id}/runs")
    assert run_response.status_code == 201, run_response.text
    body = run_response.json()
    assert body["runner_started"] is False
    assert body["total"] == 2
    assert body["missing_automation"] == 1
    assert [g["execution_key"] for g in body["groups"]] == [
        "NJM-1100", "NJM-1200"
    ]

    loaded = client.get(f"/api/runs/{body['run_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["groups"] == body["groups"]


def test_invalid_suite_not_saved():
    invalid = {**PLAN, "selected": {"NJM-1100": ["NJM-999"]}}
    response = client.post("/api/suites", json=invalid)
    assert response.status_code == 422


def test_unknown_suite_and_run_return_404():
    assert client.post("/api/suites/not-found/runs").status_code == 404
    assert client.get("/api/runs/not-found").status_code == 404
