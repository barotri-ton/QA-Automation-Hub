"""Read-only JUnit report reconciliation for FLBv3 runs."""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import APIRouter, HTTPException
from .flbv3_runner_api import _repo, _safe_run

router = APIRouter(prefix="/api/flbv3", tags=["FLBv3 results"])
KEY = re.compile(r"NJM-[0-9]+", re.I)
MAX_FILES = 500
MAX_BYTES = 12_000_000


def analyze(root: Path, run_id: str):
    folder = _safe_run(root, run_id)
    results = []
    for path in sorted(folder.rglob("*.xml")):
        if len(results) >= MAX_FILES:
            break
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            continue
        if not (path.name.lower().startswith(("junit", "pytest", "results", "report")) or "junit" in str(path).lower()):
            continue
        try:
            tree = ET.parse(path)
        except (ET.ParseError, OSError):
            continue
        for case in tree.iter("testcase"):
            name = case.get("name") or ""
            classname = case.get("classname") or ""
            key_match = KEY.search(name + " " + classname)
            if not key_match:
                continue
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")
            kind = "BROKEN" if error is not None else "FAILED" if failure is not None else "SKIPPED" if skipped is not None else "PASSED"
            node = error if error is not None else failure if failure is not None else skipped
            reason = ((node.get("message") or node.text or "") if node is not None else "").strip()[:3000]
            results.append({"key": key_match.group().upper(), "test": name,
                            "status": kind, "reason": reason,
                            "duration": case.get("time"), "report": str(path.relative_to(folder))})
    latest = {}
    for item in results:
        latest[item["key"]] = item
    counts = {k: sum(item["status"] == k for item in latest.values()) for k in ("PASSED", "FAILED", "BROKEN", "SKIPPED")}
    return {"run_id": run_id, "counts": counts, "cases": sorted(latest.values(), key=lambda item: item["key"]),
            "attempts": len(results), "reports_scanned": len(set(item["report"] for item in results)),
            "authoritative_for": "JUnit reports discovered; last matching report by filename, not guaranteed chronological",
            "jira_published": False}


@router.get("/repositories/{repository_id}/runs/{run_id}/results")
def results(repository_id: int, run_id: str):
    root = _repo(repository_id)
    try:
        return analyze(root, run_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "Cannot analyze run reports") from exc
