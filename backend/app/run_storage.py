"""Persist immutable suite snapshots and sequential run progress.

SQLite-backed storage; does not execute pytest or write to Jira.
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base
from .execution_groups import CaseStatus, SequentialRun, ExecutionGroup, CaseInstance


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class SavedSuite(Base):
    __tablename__ = "saved_suites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_key: Mapped[str] = mapped_column(String(32))
    snapshot_json: Mapped[str] = mapped_column(Text)
    selection_json: Mapped[str] = mapped_column(Text)
    mappings_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)


class SavedRun(Base):
    __tablename__ = "saved_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_id: Mapped[str] = mapped_column(ForeignKey("saved_suites.id"))
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=timestamp)
    updated_at: Mapped[str] = mapped_column(String(40), default=timestamp)


def encode_run(run: SequentialRun) -> dict:
    return {
        "id": run.id,
        "plan_key": run.plan_key,
        "cancelled": run.cancelled,
        "groups": [
            {
                "id": group.id,
                "jira_key": group.jira_key,
                "cases": [
                    {
                        "id": case.id,
                        "jira_key": case.jira_key,
                        "nodeid": case.nodeid,
                        "status": case.status.value,
                        "attempt": case.attempt,
                    }
                    for case in group.cases
                ],
            }
            for group in run.groups
        ],
    }


def decode_run(state: dict) -> SequentialRun:
    return SequentialRun(
        id=state["id"],
        plan_key=state["plan_key"],
        cancelled=state["cancelled"],
        groups=[
            ExecutionGroup(
                id=group["id"],
                jira_key=group["jira_key"],
                cases=[
                    CaseInstance(
                        id=case["id"],
                        jira_key=case["jira_key"],
                        nodeid=case["nodeid"],
                        status=CaseStatus(case["status"]),
                        attempt=case["attempt"],
                    )
                    for case in group["cases"]
                ],
            )
            for group in state["groups"]
        ],
    )


def save_suite(db: Session, snapshot: dict, selected: dict, mappings: dict) -> SavedSuite:
    suite = SavedSuite(
        id=str(uuid4()),
        plan_key=snapshot["jira_key"],
        snapshot_json=json.dumps(snapshot),
        selection_json=json.dumps(selected),
        mappings_json=json.dumps(mappings),
    )
    db.add(suite)
    db.commit()
    return suite


def save_run(db: Session, suite_id: str, run: SequentialRun) -> SavedRun:
    record = SavedRun(
        id=run.id,
        suite_id=suite_id,
        state_json=json.dumps(encode_run(run)),
    )
    db.add(record)
    db.commit()
    return record


def load_run(db: Session, run_id: str) -> SequentialRun | None:
    record = db.get(SavedRun, run_id)
    return decode_run(json.loads(record.state_json)) if record else None


def update_run(db: Session, run: SequentialRun) -> None:
    record = db.get(SavedRun, run.id)
    if record is None:
        raise KeyError("Run not found")
    record.state_json = json.dumps(encode_run(run))
    record.updated_at = timestamp()
    db.commit()
