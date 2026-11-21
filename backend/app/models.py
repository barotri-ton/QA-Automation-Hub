from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

def now():
    return datetime.now(timezone.utc)

class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    path: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class TestItem(Base):
    __tablename__ = "test_items"
    __table_args__ = (UniqueConstraint("repository_id", "nodeid"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"))
    nodeid: Mapped[str] = mapped_column(String(2048))
    jira_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    collection_status: Mapped[str] = mapped_column(String(32), default="COLLECTED")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
