"""Read-only JUnit report reconciliation for FLBv3 runs."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import APIRouter, HTTPException
from .flbv3_runner_api import _repo, _safe_run

router = APIRouter(prefix="/api/flbv3", tags=["FLBv3 results"])
KEY = re.compile(r"(?<![A-Za-z0-9])NJM[-_][0-9]+(?![0-9])", re.I)
MAX_FILES = 500
MAX_BYTES = 12_000_000
MAX_ALLURE_RESULTS = 2000
MAX_ALLURE_JSON_BYTES = 2_000_000
MAX_EVIDENCE_PER_CASE = 40


def _allure_evidence(folder: Path):
    """Index safe metadata only; never expose attachment bytes or absolute paths."""
    evidence = {}
    directory = folder / "allure-results"
    if not directory.is_dir() or directory.is_symlink():
        return evidence
    for path in sorted(directory.glob("*-result.json"))[:MAX_ALLURE_RESULTS]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ALLURE_JSON_BYTES:
                continue
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                continue
            identifiers = " ".join(str(payload.get(field) or "") for field in ("name", "fullName", "testCaseId"))
            for label in payload.get("labels", []):
                if isinstance(label, dict) and label.get("name") in ("testCaseId", "testId", "suite", "subSuite"):
                    identifiers += " " + str(label.get("value") or "")
            match = KEY.search(identifiers)
            if not match:
                continue
            key = match.group().upper().replace("_", "-")
            attachments = []
            for attachment in payload.get("attachments", []):
                if not isinstance(attachment, dict):
                    continue
                source = attachment.get("source")
                if not isinstance(source, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", source):
                    continue
                candidate = directory / source
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                attachments.append({"name": str(attachment.get("name") or "Evidence")[:120],
                                    "type": str(attachment.get("type") or "")[:100],
                                    "source": source, "available": True})
                if len(attachments) >= MAX_EVIDENCE_PER_CASE:
                    break
            evidence.setdefault(key, []).append({
                "result_file": path.name, "uuid": str(payload.get("uuid") or "")[:100],
                "status": str(payload.get("status") or "unknown")[:30],
                "start": payload.get("start") if isinstance(payload.get("start"), (int, float)) else None,
                "stop": payload.get("stop") if isinstance(payload.get("stop"), (int, float)) else None,
                "attachments": attachments,
            })
        except (OSError, ValueError, UnicodeError, TypeError):
            continue
    return evidence



def analyze(root: Path, run_id: str):
    folder = _safe_run(root, run_id)
    results = []
    candidates = []
    for path in folder.rglob("*.xml"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if not (path.name.lower().startswith(("junit", "pytest", "results", "report")) or "junit" in str(path).lower()):
                continue
            stat = path.stat()
            if stat.st_size <= MAX_BYTES:
                candidates.append((stat.st_mtime_ns, str(path), path))
        except OSError:
            continue
    candidates.sort()
    reports_scanned = 0
    for _, _, path in candidates[:MAX_FILES]:
        reports_scanned += 1
        try:
            # Reject DTD/entity expansion and avoid parsing unbounded external XML.
            with path.open("rb") as stream:
                header = stream.read(4096)
                if b"<!DOCTYPE" in header.upper() or b"<!ENTITY" in header.upper():
                    continue
                stream.seek(0)
                tree = ET.parse(stream)
        except (ET.ParseError, OSError, ValueError):
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
            results.append({"key": key_match.group().upper().replace("_", "-"), "test": name,
                            "status": kind, "reason": reason,
                            "duration": case.get("time"), "report": str(path.relative_to(folder))})
    allure = _allure_evidence(folder)
    latest = {}
    attempts_by_key = {}
    for item in results:
        attempts_by_key.setdefault(item["key"], []).append(item)
        latest[item["key"]] = item
    for key, item in latest.items():
        # Filesystem mtime does not establish attempt order. Preserve all observed
        # outcomes and flag conflicting retry statuses for human reconciliation.
        observed = sorted({attempt["status"] for attempt in attempts_by_key[key]})
        item["allure_results"] = allure.get(key, [])
        item["evidence_count"] = sum(len(record["attachments"]) for record in item["allure_results"])
        item["observed_statuses"] = observed
        item["display_status_is_provisional"] = True
        item["retry_conflict"] = len(observed) > 1
        item["final_verdict_verified"] = False
        item["needs_verdict_review"] = len(attempts_by_key[key]) > 1
        item["attempts"] = len(attempts_by_key[key])
        item["history"] = attempts_by_key[key][:-1]
        item["verdict_confidence"] = "PROVISIONAL_FILE_MTIME"
    counts = {k: sum(item["status"] == k for item in latest.values()) for k in ("PASSED", "FAILED", "BROKEN", "SKIPPED")}
    # Do not misrepresent file-mtime-derived counts as verified final outcomes.
    verified_counts = {k: 0 for k in ("PASSED", "FAILED", "BROKEN", "SKIPPED")}
    provisional_count = len(latest)
    return {"run_id": run_id, "counts": counts, "cases": sorted(latest.values(), key=lambda item: item["key"]),
            "attempts": len(results), "reports_scanned": reports_scanned,
            "counts_are_provisional": True, "verified_counts": verified_counts,
            "provisional_count": provisional_count,
            "allure_cases_with_evidence": sum(bool(item["evidence_count"]) for item in latest.values()),
            "retry_review_required": sum(item["needs_verdict_review"] for item in latest.values()),
            "conflicting_retry_outcomes": sum(item["retry_conflict"] for item in latest.values()),
            "authoritative_for": "JUnit reports ordered by filesystem modification time; provisional when retries or concurrent writes exist",
            "jira_published": False}


@router.get("/repositories/{repository_id}/runs/{run_id}/results")
def results(repository_id: int, run_id: str):
    root = _repo(repository_id)
    try:
        return analyze(root, run_id)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, "Cannot analyze run reports") from exc
