"""Local development suite/run persistence endpoints.

These endpoints do not launch tests or connect to Jira. No authentication is
implemented; the service MUST be bound to loopback.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .database import Base, engine, SessionLocal
from .execution_groups import CaseStatus
from .run_storage import SavedSuite, SavedRun, save_suite, save_run, load_run, update_run
from .xray_preview import SuitePayload, make_snapshot
from .xray_suite import SuiteSelection, build_sequential_run

router = APIRouter(prefix="/api", tags=["Saved suites and runs"])
Base.metadata.create_all(engine)


def get_db():
    with SessionLocal() as db:
        yield db


@router.post("/suites", status_code=201)
def create_suite(payload: SuitePayload, db: Session = Depends(get_db)):
    try:
        snapshot = make_snapshot(payload)
        selection = SuiteSelection({
            key: frozenset(values) for key, values in payload.selected.items()
        })
        build_sequential_run(snapshot, selection, payload.mappings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    record = save_suite(
        db,
        payload.model_dump(exclude={"selected", "mappings"}),
        payload.selected,
        payload.mappings,
    )
    return {"suite_id": record.id, "plan_key": record.plan_key, "mode": "SEQUENTIAL"}


@router.get("/suites")
def list_suites(db: Session = Depends(get_db)):
    return [
        {"suite_id": suite.id, "plan_key": suite.plan_key, "created_at": suite.created_at}
        for suite in db.scalars(select(SavedSuite).order_by(SavedSuite.created_at.desc()))
    ]


@router.post("/suites/{suite_id}/runs", status_code=201)
def create_run(suite_id: str, db: Session = Depends(get_db)):
    import json
    from .xray_preview import PlanPayload
    suite = db.get(SavedSuite, suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")
    payload = PlanPayload.model_validate({
        **json.loads(suite.snapshot_json),
        "mappings": json.loads(suite.mappings_json),
    })
    run = build_sequential_run(
        make_snapshot(payload),
        SuiteSelection({
            key: frozenset(values)
            for key, values in json.loads(suite.selection_json).items()
        }),
        payload.mappings,
    )
    save_run(db, suite_id, run)
    return {"run_id": run.id, "runner_started": False, **run.summary()}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = load_run(db, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return {"runner_started": False, **run.summary()}


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    return [
        {"run_id": record.id, "suite_id": record.suite_id, "updated_at": record.updated_at}
        for record in db.scalars(select(SavedRun).order_by(SavedRun.created_at.desc()))
    ]
