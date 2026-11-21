import os
from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, SessionLocal, engine
from .discovery import collect_tests
from .models import Repository, TestItem, now

Base.metadata.create_all(engine)
app = FastAPI(title="QA Automation Hub", version="0.1.0")

class RepoInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1)


def get_db():
    with SessionLocal() as db:
        yield db


def repo_dict(repo):
    return {"id": repo.id, "name": repo.name, "path": repo.path}

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

@app.get("/api/repositories")
def repositories(db: Session = Depends(get_db)):
    return [repo_dict(r) for r in db.scalars(select(Repository).order_by(Repository.id))]

@app.post("/api/repositories", status_code=201)
def register(payload: RepoInput, db: Session = Depends(get_db)):
    if os.getenv("QA_HUB_ALLOW_LOCAL_PATHS", "false").lower() != "true":
        raise HTTPException(403, "Local path registration disabled; set QA_HUB_ALLOW_LOCAL_PATHS=true on a trusted local machine")
    path = Path(payload.path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(400, "Repository directory does not exist")
    if db.scalar(select(Repository).where(Repository.name == payload.name)):
        raise HTTPException(409, "Repository name already exists")
    repo = Repository(name=payload.name, path=str(path))
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo_dict(repo)

@app.post("/api/repositories/{repo_id}/scan")
def scan(repo_id: int, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    try:
        collected = collect_tests(Path(repo.path))
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    existing = {x.nodeid: x for x in db.scalars(select(TestItem).where(TestItem.repository_id == repo_id))}
    seen = set()
    for item in collected:
        nodeid = item["nodeid"]
        seen.add(nodeid)
        record = existing.get(nodeid)
        if record is None:
            record = TestItem(repository_id=repo_id, nodeid=nodeid)
            db.add(record)
        record.jira_key = item["jira_keys"][0] if len(item["jira_keys"]) == 1 else None
        record.collection_status = "COLLECTED" if len(item["jira_keys"]) <= 1 else "AMBIGUOUS_MAPPING"
        record.last_seen_at = now()
    for nodeid, record in existing.items():
        if nodeid not in seen:
            record.collection_status = "MISSING_FROM_COLLECTION"
    db.commit()
    return {"collected": len(collected), "mapped": sum(len(x["jira_keys"]) == 1 for x in collected), "unmapped": sum(not x["jira_keys"] for x in collected), "ambiguous": sum(len(x["jira_keys"]) > 1 for x in collected)}

@app.get("/api/repositories/{repo_id}/tests")
def tests(repo_id: int, db: Session = Depends(get_db)):
    if not db.get(Repository, repo_id):
        raise HTTPException(404, "Repository not found")
    return [{"nodeid": t.nodeid, "jira_key": t.jira_key, "status": t.collection_status} for t in db.scalars(select(TestItem).where(TestItem.repository_id == repo_id).order_by(TestItem.nodeid))]
