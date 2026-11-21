"""Opt-in local worker for trusted pytest repositories.

Single process-local worker; no distributed lock or crash recovery yet.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path

from sqlalchemy import select

from .database import SessionLocal
from .local_runner import run_sequential
from .models import Repository
from .run_storage import SavedRun, load_run, update_run

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qa-hub-runner")
_lock = Lock()
_active_run: str | None = None


def active_run_id() -> str | None:
    with _lock:
        return _active_run


def launch_run(run_id: str, repository_id: int) -> None:
    """Launch only when explicitly enabled on a trusted local machine."""
    global _active_run
    if os.getenv("QA_HUB_ENABLE_RUNNER", "false").lower() != "true":
        raise PermissionError("Runner disabled; set QA_HUB_ENABLE_RUNNER=true locally")
    with _lock:
        if _active_run is not None:
            raise RuntimeError("Another run is already active")
        with SessionLocal() as db:
            repo = db.get(Repository, repository_id)
            record = db.get(SavedRun, run_id)
            if not repo or not record:
                raise LookupError("Run or repository not found")
            run = load_run(db, run_id)
            if run is None or run.cancelled or run.summary()["completed"]:
                raise ValueError("Run is not in a fresh queued state")
            if not run.next_case():
                raise ValueError("No runnable test cases in this run")
            path = Path(repo.path).resolve()
            if not path.is_dir():
                raise ValueError("Repository directory is unavailable")
            # All runnable node IDs must match a discovered, unambiguous
            # item in the selected trusted repository.
            from .models import TestItem
            valid = {
                (test.jira_key, test.nodeid)
                for test in db.scalars(
                    select(TestItem).where(
                        TestItem.repository_id == repository_id,
                        TestItem.collection_status == "COLLECTED",
                        TestItem.jira_key.is_not(None),
                    )
                )
            }
            for group in run.groups:
                for case in group.cases:
                    if case.nodeid and (case.jira_key, case.nodeid) not in valid:
                        raise ValueError(
                            "Suite mapping does not match scanned repository inventory"
                        )
        _active_run = run_id
        try:
            _executor.submit(_worker, run_id, path)
        except Exception:
            _active_run = None
            raise


def _worker(run_id: str, path: Path) -> None:
    global _active_run
    try:
        with SessionLocal() as db:
            run = load_run(db, run_id)
            if run is None:
                return

            def persist(updated):
                update_run(db, updated)

            try:
                run_sequential(run, path, on_update=persist)
            except Exception:
                # Unexpected infrastructure failure: mark unfinished cases
                # as ERROR/CANCELLED rather than leaving RUNNING forever.
                from .execution_groups import CaseStatus
                for group in run.groups:
                    for case in group.cases:
                        if case.status == CaseStatus.RUNNING:
                            case.status = CaseStatus.ERROR
                        elif case.status == CaseStatus.QUEUED:
                            case.status = CaseStatus.CANCELLED
                update_run(db, run)
    finally:
        with _lock:
            _active_run = None
