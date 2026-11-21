"""Read-only investigation bundle: Jira case, execution run, and local JUnit evidence.

This endpoint does not classify failures or modify Jira.
"""
from fastapi import APIRouter, HTTPException, Query
from . import jira_api
from .flbv3_results import analyze
from .flbv3_runner_api import _repo
from .spec_references import SpecReference, serialize
from .database import SessionLocal
from sqlalchemy import select

router = APIRouter(prefix="/api/investigations", tags=["Investigation bundles"])


@router.get("/repositories/{repository_id}/runs/{run_id}/tests/{test_key}")
def investigate(
    repository_id: int,
    run_id: str,
    test_key: str,
    test_run_id: int | None = Query(default=None, ge=1),
    include_jira: bool = True,
):
    jira_api._key(test_key)
    try:
        report = analyze(_repo(repository_id), run_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "Unable to read run evidence") from exc
    matched = next((case for case in report["cases"] if case["key"] == test_key), None)
    if matched is None:
        raise HTTPException(404, "Test case not found in JUnit run")
    jira = None
    jira_error = None
    xray_run = None
    if include_jira:
        try:
            jira = jira_api.test_details(test_key)
        except HTTPException as exc:
            jira_error = {"status": exc.status_code, "message": exc.detail}
        if test_run_id is not None:
            try:
                xray_run = jira_api.run_details(test_run_id)
            except HTTPException as exc:
                jira_error = {"status": exc.status_code, "message": exc.detail}
    with SessionLocal() as db:
        spec = db.scalar(select(SpecReference).where(SpecReference.test_key == test_key))
        spec_data = serialize(spec) if spec is not None else None
    return {
        "test_key": test_key,
        "run_id": run_id,
        "test_run_id": test_run_id,
        "runner_evidence": matched,
        "jira_test": jira,
        "xray_test_run": xray_run,
        "jira_error": jira_error,
        "specification": ({"state": "MANUALLY_CURATED", **spec_data} if spec_data else {
            "state": "NOT_CONNECTED",
            "message": "No verified specification source. Attach or consult the current spec before classification.",
        }),
        "classification": "INCONCLUSIVE",
        "classification_is_automatic": False,
        "jira_published": False,
        "provenance": {
            "runner": "local JUnit XML",
            "jira": "read-only Jira/Xray when configured",
            "specification": "locally curated and unverified" if spec_data else "unavailable",
            "verdict": "provisional; report file mtime ordering",
        },
    }
