"""Review-only decision records. Publishing is deliberately separate."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, SessionLocal, engine

router = APIRouter(prefix="/api/reviews", tags=["Failure reviews"])
KINDS = {"PRODUCT_BUG", "OBSOLETE_TC", "AUTOMATION_ISSUE", "ENVIRONMENT_ISSUE", "INCONCLUSIVE"}


class FailureReview(Base):
    __tablename__ = "failure_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), index=True)
    test_key: Mapped[str] = mapped_column(String(32))
    classification: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    jira_defect_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewer: Mapped[str] = mapped_column(String(120))
    reviewed_at: Mapped[str] = mapped_column(String(40))


Base.metadata.create_all(engine)


def db_session():
    with SessionLocal() as db:
        yield db


class ReviewInput(BaseModel):
    run_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")
    test_key: str = Field(pattern=r"^NJM-[0-9]+$")
    classification: str
    reason: str = Field(min_length=10, max_length=20000)
    jira_defect_key: str | None = Field(default=None, pattern=r"^NJM-[0-9]+$")
    reviewer: str = Field(min_length=1, max_length=120)


@router.put("")
def upsert_review(payload: ReviewInput, db: Session = Depends(db_session)):
    if payload.classification not in KINDS:
        raise HTTPException(422, "Unknown failure classification")
    row = db.scalar(select(FailureReview).where(
        FailureReview.run_id == payload.run_id,
        FailureReview.test_key == payload.test_key))
    if row is None:
        row = FailureReview(run_id=payload.run_id, test_key=payload.test_key)
        db.add(row)
    row.classification = payload.classification
    row.reason = payload.reason
    row.jira_defect_key = payload.jira_defect_key
    row.reviewer = payload.reviewer
    row.reviewed_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(row)
    return {"id": row.id, "saved": True, "jira_published": False}


@router.get("/{run_id}")
def list_reviews(run_id: str, db: Session = Depends(db_session)):
    if not run_id or len(run_id) > 128 or not all(c.isalnum() or c in "_.-" for c in run_id):
        raise HTTPException(422, "Invalid run ID")
    rows = db.scalars(select(FailureReview).where(FailureReview.run_id == run_id)).all()
    return [{"id": r.id, "run_id": r.run_id, "test_key": r.test_key,
             "classification": r.classification, "reason": r.reason,
             "jira_defect_key": r.jira_defect_key, "reviewer": r.reviewer,
             "reviewed_at": r.reviewed_at} for r in rows]
