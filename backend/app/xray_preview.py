"""Preview-only API for Xray plan review and sequential suite building.

Input is a client-supplied snapshot, NOT a live Jira import. This endpoint
does not execute tests, persist runs, or write results to Jira.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .xray_suite import (
    SuiteSelection, XrayCase, XrayExecution, XrayPlanSnapshot,
    build_sequential_run, review_plan,
)

router = APIRouter(prefix="/api/xray/preview", tags=["Xray preview"])


class CasePayload(BaseModel):
    jira_key: str = Field(pattern=r"^NJM-[0-9]+$")
    summary: str = ""
    test_run_id: int | None = Field(default=None, ge=1)
    xray_status: str | None = None
    rank: int | None = None
    archived: bool = False


class ExecutionPayload(BaseModel):
    jira_key: str = Field(pattern=r"^NJM-[0-9]+$")
    summary: str = ""
    cases: list[CasePayload] = Field(max_length=5000)


class PlanPayload(BaseModel):
    jira_key: str = Field(pattern=r"^NJM-[0-9]+$")
    executions: list[ExecutionPayload] = Field(max_length=500)
    mappings: dict[str, str] = Field(default_factory=dict)


class SuitePayload(PlanPayload):
    selected: dict[str, list[str]]


def make_snapshot(payload: PlanPayload) -> XrayPlanSnapshot:
    return XrayPlanSnapshot(
        jira_key=payload.jira_key,
        executions=tuple(
            XrayExecution(
                jira_key=execution.jira_key,
                summary=execution.summary,
                cases=tuple(
                    XrayCase(jira_key=case.jira_key, summary=case.summary)
                    for case in execution.cases
                ),
            )
            for execution in payload.executions
        ),
    )


@router.post("/review")
def review(payload: PlanPayload):
    try:
        return review_plan(make_snapshot(payload), payload.mappings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/suite")
def preview_suite(payload: SuitePayload):
    try:
        snapshot = make_snapshot(payload)
        run = build_sequential_run(
            snapshot,
            SuiteSelection({
                key: frozenset(values)
                for key, values in payload.selected.items()
            }),
            payload.mappings,
        )
        return {
            "mode": "SEQUENTIAL",
            "preview_only": True,
            "snapshot_revision": snapshot.revision,
            "run": run.summary(),
            "cases": [
                {
                    "execution_key": group.jira_key,
                    "case_instances": [
                        {
                            "jira_key": case.jira_key,
                            "nodeid": case.nodeid,
                            "status": case.status.value,
                        }
                        for case in group.cases
                    ],
                }
                for group in run.groups
            ],
        }
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
