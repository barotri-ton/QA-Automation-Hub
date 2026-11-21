"""Manual specification verification markers. No specification fetching or validation."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, SessionLocal
from .jira_api import _key

router = APIRouter(prefix="/api/spec-checks", tags=["Manual spec checks"])
STATES = {"NOT_VERIFIED", "VERIFIED", "NEEDS_UPDATE"}


class SpecCheck(Base):
    __tablename__ = "spec_checks"
    __table_args__ = (UniqueConstraint("run_id", "test_key", name="uq_spec_check_run_test"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    test_key: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[str] = mapped_column(String(40))


class SpecCheckInput(BaseModel):
    repository_id: int = Field(ge=1)
    run_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    test_key: str = Field(pattern=r"^NJM-[0-9]+$")
    status: str
    failed_reason_unclear: bool = False
    note: str = Field(default="", max_length=5000)
    reviewer: str = Field(min_length=1, max_length=120)


def session():
    with SessionLocal() as db:
        yield db


def serialize(row):
    return {"run_id": row.run_id, "test_key": row.test_key, "status": row.status,
            "note": row.note, "reviewer": row.reviewer, "updated_at": row.updated_at,
            "manual_only": True}


@router.put("")
def save(payload: SpecCheckInput, db: Session = Depends(session)):
    if not payload.failed_reason_unclear:
        raise HTTPException(422, "Spec marker requires a FAILED test with an unresolved failure reason; confirm eligibility in review")
    # Server-side evidence check: client confirmation alone is not sufficient.
    from .flbv3_runner_api import _repo
    from .flbv3_results import analyze
    try:
        report = analyze(_repo(payload.repository_id), payload.run_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "Unable to validate runner evidence for spec check") from exc
    case = next((item for item in report["cases"] if item["key"] == payload.test_key), None)
    if case is None or case["status"] != "FAILED" or case.get("needs_verdict_review", False):
        raise HTTPException(422, "Spec check requires a FAILED case without unresolved retry verdict; reconcile retries first")
    if payload.status not in STATES:
        raise HTTPException(422, "Invalid manual spec verification status")
    row = db.scalar(select(SpecCheck).where(
        SpecCheck.run_id == payload.run_id, SpecCheck.test_key == payload.test_key))
    if row is None:
        row = SpecCheck(run_id=payload.run_id, test_key=payload.test_key)
        db.add(row)
    row.status = payload.status
    row.note = payload.note
    row.reviewer = payload.reviewer
    row.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return serialize(row)


@router.get("/{run_id}")
def list_checks(run_id: str, db: Session = Depends(session)):
    if not run_id or len(run_id) > 128 or not all(c.isalnum() or c in "_.-" for c in run_id):
        raise HTTPException(422, "Invalid run ID")
    return [serialize(row) for row in db.scalars(select(SpecCheck).where(SpecCheck.run_id == run_id))]


@router.get("/{run_id}/{test_key}")
def get_check(run_id: str, test_key: str, db: Session = Depends(session)):
    _key(test_key)
    if not run_id or len(run_id) > 128 or not all(c.isalnum() or c in "_.-" for c in run_id):
        raise HTTPException(422, "Invalid run ID")
    row = db.scalar(select(SpecCheck).where(SpecCheck.run_id == run_id, SpecCheck.test_key == test_key))
    return serialize(row) if row else {"run_id": run_id, "test_key": test_key, "status": "NOT_VERIFIED",
                                       "note": "", "reviewer": "", "updated_at": None, "manual_only": True}
