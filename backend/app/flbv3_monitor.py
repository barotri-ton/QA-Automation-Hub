"""Read-only FLBv3 runner-events monitor. Never invokes automation."""
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Repository

router = APIRouter(prefix="/api/flbv3", tags=["FLBv3 monitoring"])
RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
KEY = re.compile(r"^NJM-[0-9]+$")


def get_db():
    with SessionLocal() as db:
        yield db


def read_monitor(repo_root: Path, run_id: str, limit: int = 200):
    if not RUN_NAME.fullmatch(run_id) or run_id in (".", ".."):
        raise ValueError("Invalid run ID")
    root = (repo_root / "results" / "runs").resolve()
    folder = (root / run_id).resolve()
    if folder.parent != root or not folder.is_dir():
        raise FileNotFoundError("Run directory not found")
    marker = folder / "flbv3-run.json"
    if not marker.is_file():
        raise FileNotFoundError("Not an FLBv3 run")
    meta = json.loads(marker.read_text(encoding="utf-8-sig"))
    planned = [x for x in meta.get("planned_keys", []) if isinstance(x, str) and KEY.fullmatch(x)]
    events = []
    event_dir = folder / "allure-results" / "runner-events"
    if event_dir.is_dir() and not event_dir.is_symlink():
        for file in sorted(event_dir.glob("*.jsonl")):
            if file.is_symlink() or not file.is_file():
                continue
            # Bound memory and avoid reading huge or untrusted log files.
            if file.stat().st_size > 20_000_000:
                continue
            with file.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if len(line) > 65536:
                        continue
                    try:
                        event = json.loads(line)
                    except (ValueError, TypeError):
                        continue  # partially written JSONL line
                    if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                        continue
                    events.append(event)
    def timestamp(event):
        try:
            return float(event.get("ts") or 0)
        except (TypeError, ValueError, OverflowError):
            return 0.0
    events.sort(key=lambda e: (timestamp(e), str(e.get("run") or "")))
    states = {key: {"key": key, "status": "PLANNED", "attempts": 0} for key in planned}
    active = {}
    for event in events:
        key = event.get("key")
        kind = event["event"]
        if not isinstance(key, str) or not KEY.fullmatch(key):
            continue
        row = states.setdefault(key, {"key": key, "status": "PLANNED", "attempts": 0})
        if kind in ("file_started", "test_started"):
            if kind == "file_started":
                row["attempts"] += 1
            row["status"] = "RUNNING"
            row["started_at"] = event.get("ts")
            if kind == "file_started":
                active[key] = {"key": key, "pid": event.get("child_pid"), "file": event.get("file")}
        elif kind == "file_finished":
            row["status"] = ("BROKEN" if event.get("timeout") or event.get("exit") not in (0, 1)
                             else "PASSED" if event.get("exit") == 0 else "FAILED")
            row["finished_at"] = event.get("ts")
            active.pop(key, None)
        elif kind == "test_completed":
            # Pytest event schema varies; retain file-level status as authority.
            row["last_test_event"] = event.get("ts")
    return {
        "run_id": run_id, "state": meta.get("state"), "started_at": meta.get("started_at"),
        "finished_at": meta.get("finished_at"), "planned": len(planned),
        "cases": sorted(states.values(), key=lambda x: x["key"]),
        "active_workers": list(active.values()),
        "recent_events": events[-limit:],
        "event_count": len(events),
        "note": "Event statuses are provisional; use JUnit/Allure for final test verdicts.",
    }


@router.get("/repositories/{repository_id}/runs/{run_id}/monitor")
def monitor(repository_id: int, run_id: str, limit: int = Query(100, ge=1, le=500),
            db: Session = Depends(get_db)):
    repo = db.get(Repository, repository_id)
    if not repo:
        raise HTTPException(404, "Repository not found")
    try:
        return read_monitor(Path(repo.path), run_id, limit)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Invalid or unreadable run data") from exc
