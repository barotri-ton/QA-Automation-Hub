"""Read-only Jira Server/DC + Xray Raven adapter. Credentials remain server-side."""
import os
import re

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/jira", tags=["Jira/Xray read-only"])
KEY = re.compile(r"^NJM-[0-9]+$")
BASE_DEFAULT = "http://10.170.180.181:8080"


def _client():
    from .jira_connection import effective_credentials
    base, token = effective_credentials()
    if not token:
        raise HTTPException(503, "Jira PAT not configured on backend")
    base = base.rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise HTTPException(503, "Invalid Jira base URL")
    return httpx.Client(base_url=base, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                        timeout=25, follow_redirects=False)


def _get(client, path, params=None):
    try:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Jira request timed out") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        raise HTTPException(502, f"Jira returned HTTP {status}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, "Jira request failed or returned invalid JSON") from exc


def _key(value):
    if not KEY.fullmatch(value):
        raise HTTPException(422, "Invalid NJM issue key")
    return value


def _paged(client, path, *, detailed=False, max_pages=100):
    results = []
    for page in range(1, max_pages + 1):
        params = {"page": page, "limit": 100}
        if detailed:
            params["detailed"] = "true"
        batch = _get(client, path, params)
        if not isinstance(batch, list):
            raise HTTPException(502, "Unexpected Xray pagination response")
        results.extend(batch)
        if len(batch) < 100:
            return results
    raise HTTPException(502, "Xray pagination safety limit exceeded")


@router.get("/plans/{plan_key}/snapshot")
def plan_snapshot(plan_key: str):
    """Import execution-scoped membership; never deduplicate across executions."""
    plan_key = _key(plan_key)
    with _client() as client:
        issue = _get(client, f"/rest/api/2/issue/{plan_key}",
                     {"fields": "issuetype,summary,status,fixVersions"})
        raw_executions = _get(client, f"/rest/raven/1.0/api/testplan/{plan_key}/testexecution")
        if not isinstance(raw_executions, list):
            raise HTTPException(502, "Unexpected Test Plan executions response")
        executions = []
        for item in raw_executions:
            key = _key(item["key"])
            runs = _paged(client, f"/rest/raven/1.0/api/testexec/{key}/test", detailed=True)
            cases = []
            for run in runs:
                test_key = _key(run["key"])
                cases.append({
                    "jira_key": test_key,
                    "summary": run.get("summary") or "",
                    "test_run_id": run.get("id"),
                    "xray_status": run.get("status"),
                    "rank": run.get("rank"),
                    "archived": run.get("archived", False),
                })
            # Preserve server ordering; do not globally deduplicate Test keys.
            executions.append({"jira_key": key, "summary": item.get("summary") or "",
                               "cases": cases, "archived": item.get("archived", False)})
    return {"jira_key": plan_key, "summary": issue.get("fields", {}).get("summary"),
            "issue_type": issue.get("fields", {}).get("issuetype", {}).get("name"),
            "executions": executions, "mappings": {}, "source": "jira_xray_live"}


@router.get("/tests/{test_key}")
def test_details(test_key: str):
    test_key = _key(test_key)
    with _client() as client:
        issue = _get(client, f"/rest/api/2/issue/{test_key}",
                     {"fields": "summary,description,customfield_10704,customfield_10700,customfield_10708,issuelinks,attachment,labels,components"})
        steps = _get(client, f"/rest/raven/1.0/api/test/{test_key}/step")
        history = _get(client, f"/rest/raven/1.0/api/test/{test_key}/testruns")
    return {"issue": issue, "steps": steps, "history": history}


@router.get("/runs/{run_id}")
def run_details(run_id: int):
    if run_id < 1:
        raise HTTPException(422, "Invalid Test Run ID")
    with _client() as client:
        run = _get(client, f"/rest/raven/1.0/api/testrun/{run_id}")
        steps = _get(client, f"/rest/raven/1.0/api/testrun/{run_id}/step")
        defects = _get(client, f"/rest/raven/1.0/api/testrun/{run_id}/defect")
        attachments = _get(client, f"/rest/raven/1.0/api/testrun/{run_id}/attachment")
    return {"run": run, "steps": steps, "defects": defects, "attachments": attachments}


@router.get("/issues/{issue_key}")
def issue_details(issue_key: str):
    issue_key = _key(issue_key)
    with _client() as client:
        return _get(client, f"/rest/api/2/issue/{issue_key}",
                    {"fields": "issuetype,summary,description,status,priority,fixVersions,issuelinks,attachment"})


@router.get("/statuses")
def statuses():
    with _client() as client:
        return {"test_statuses": _get(client, "/rest/raven/1.0/api/settings/teststatuses"),
                "step_statuses": _get(client, "/rest/raven/1.0/api/settings/teststepstatuses")}
