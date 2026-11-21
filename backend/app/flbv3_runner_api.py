"""Opt-in local PowerShell FLBv3 process manager.

Requires a single uvicorn worker on a trusted loopback-bound Windows host.
No Jira writes and no modification of the automation repository.
"""
import os
import re
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Repository
from .runner_worker import active_run_id

router = APIRouter(prefix="/api/flbv3", tags=["FLBv3 local runner"])
_guard = threading.Lock()
_process = None
_identity = None
KEY = re.compile(r"^NJM-[0-9]+$")
RUN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$")
GATES = frozenset({"repo-maintenance", "tape", "flr-to-source", "destructive", "license"})


class Launch(BaseModel):
    repository_id: int
    waves: list[int] = Field(default_factory=lambda: list(range(1, 9)))
    parallel: int = Field(default=5, ge=1, le=6)
    allow: list[str] = Field(default_factory=list)
    confirm_gated: bool = False
    run_id: str | None = None
    retry: bool = False
    only: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


def _enabled():
    if os.name != "nt" or os.getenv("QA_HUB_ENABLE_FLBV3_RUNNER") != "true":
        raise HTTPException(403, "FLBv3 runner requires Windows and explicit local opt-in")


def _repo(repo_id):
    with SessionLocal() as db:
        repo = db.get(Repository, repo_id)
        if not repo:
            raise HTTPException(404, "Repository not registered")
        root = Path(repo.path).resolve()
    if not root.is_dir():
        raise HTTPException(422, "Repository directory missing")
    return root


def _safe_run(root, name):
    if not name or not RUN.fullmatch(name) or name in (".", ".."):
        raise HTTPException(422, "Invalid run folder")
    runs = (root / "results" / "runs").resolve()
    path = (runs / name).resolve()
    if path.parent != runs or not (path / "flbv3-run.json").is_file():
        raise HTTPException(422, "Existing FLBv3 run not found")
    return path


def _active():
    return _process is not None and _process.poll() is None


@router.get("/runner/status")
def status():
    with _guard:
        return {"active": _active(), "pid": _process.pid if _active() else None,
                "run": _identity if _active() else None}


@router.post("/runner/start", status_code=202)
def start(payload: Launch):
    global _process, _identity
    _enabled()
    if not payload.retry and payload.run_id:
        raise HTTPException(422, "Full runs must create a fresh runner-generated directory")
    if payload.retry and not payload.run_id:
        raise HTTPException(422, "Retry requires explicit run_id")
    if not payload.retry and (payload.only or payload.exclude):
        raise HTTPException(422, "Only/exclude are retry-only")
    if any(w not in range(1, 10) for w in payload.waves) or len(set(payload.waves)) != len(payload.waves):
        raise HTTPException(422, "Invalid or repeated wave")
    if not payload.waves and not payload.retry:
        raise HTTPException(422, "Select at least one wave")
    if any(g not in GATES for g in payload.allow) or len(set(payload.allow)) != len(payload.allow):
        raise HTTPException(422, "Invalid gate")
    if (payload.allow or 9 in payload.waves) and not payload.confirm_gated:
        raise HTTPException(422, "Gated operations require explicit confirmation")
    if any(not KEY.fullmatch(k) for k in payload.only + payload.exclude):
        raise HTTPException(422, "Invalid TC key")
    root = _repo(payload.repository_id)
    script = root / "scripts" / "flbv3" / ("run_flbv3_retry.ps1" if payload.retry else "run_flbv3.ps1")
    if not script.is_file():
        raise HTTPException(422, "Expected trusted runner script missing")
    # RunDir must be an existing run; new full runs use runner-generated folders.
    args = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(script)]
    if payload.retry:
        args += ["-RunDir", str(_safe_run(root, payload.run_id)),
                 "-Parallel", str(payload.parallel)]
        if payload.only:
            args += ["-Only", ",".join(payload.only)]
        if payload.exclude:
            args += ["-Exclude", ",".join(payload.exclude)]
    else:
        args += ["-Waves", ",".join(str(w) for w in payload.waves),
                 "-Parallel", str(payload.parallel)]
    # Explicit empty Allow overrides unsafe defaults in upstream runner scripts.
    args += ["-Allow", ",".join(payload.allow)]
    with _guard:
        if _active() or active_run_id() is not None:
            raise HTTPException(409, "A local runner is already active")
        # Windows CREATE_NEW_PROCESS_GROUP allows explicit stop through taskkill.
        try:
            proc = subprocess.Popen(args, cwd=root, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        except OSError as exc:
            raise HTTPException(502, "Could not launch PowerShell runner") from exc
        _process = proc
        _identity = {"repository_id": payload.repository_id, "run_id": payload.run_id,
                     "retry": payload.retry, "waves": payload.waves}
        return {"accepted": True, "pid": proc.pid, "run": _identity}


@router.post("/runner/stop", status_code=202)
def stop():
    _enabled()
    with _guard:
        if not _active():
            raise HTTPException(409, "No managed FLBv3 process active")
        pid = _process.pid
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                capture_output=True, timeout=20, check=False)
        if result.returncode != 0:
            raise HTTPException(502, "Unable to stop runner process tree")
        return {"stop_requested": True, "pid": pid}
