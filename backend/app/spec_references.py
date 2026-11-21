"""Locally curated specification references for human-reviewed TC investigations.

No Confluence connection or automatic specification verification is implied.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, select, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, Session
from .database import Base, SessionLocal, engine
from .jira_api import _key

router = APIRouter(prefix="/api/spec-references", tags=["Specification references"])


class SpecReference(Base):
    __tablename__ = "spec_references"
    __table_args__ = (UniqueConstraint("test_key", name="uq_spec_test_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    test_key: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(240))
    source_url: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(120))
    expected_behavior: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[str] = mapped_column(String(40))


class SpecInput(BaseModel):
    test_key: str = Field(pattern=r"^NJM-[0-9]+$")
    title: str = Field(min_length=3, max_length=240)
    source_url: str = Field(min_length=8, max_length=2048)
    version: str = Field(min_length=1, max_length=120)
    expected_behavior: str = Field(min_length=10, max_length=20000)
    author: str = Field(min_length=1, max_length=120)


def session():
    with SessionLocal() as db:
        yield db


def serialize(row):
    return {"test_key": row.test_key, "title": row.title, "source_url": row.source_url,
            "version": row.version, "expected_behavior": row.expected_behavior,
            "author": row.author, "updated_at": row.updated_at,
            "verification": "MANUALLY_SUPPLIED_NOT_AUTOMATICALLY_VERIFIED"}


@router.put("")
def upsert(payload: SpecInput, db: Session = Depends(session)):
    parsed = urlparse(payload.source_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "A normal HTTP(S) specification reference URL is required")
    row = db.scalar(select(SpecReference).where(SpecReference.test_key == payload.test_key))
    if row is None:
        row = SpecReference(test_key=payload.test_key)
        db.add(row)
    row.title = payload.title
    row.source_url = payload.source_url
    row.version = payload.version
    row.expected_behavior = payload.expected_behavior
    row.author = payload.author
    row.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    return serialize(row)


@router.get("/{test_key}")
def get_reference(test_key: str, db: Session = Depends(session)):
    _key(test_key)
    row = db.scalar(select(SpecReference).where(SpecReference.test_key == test_key))
    if row is None:
        raise HTTPException(404, "No specification reference registered for this test")
    return serialize(row)
