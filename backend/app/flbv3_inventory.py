"""Safe read-only discovery of FLBv3 run folders."""
import json
from fastapi import APIRouter, HTTPException, Query
from .flbv3_runner_api import _repo

router = APIRouter(prefix="/api/flbv3", tags=["FLBv3 run inventory"])


@router.get("/repositories/{repository_id}/runs")
def list_runs(repository_id: int, limit: int = Query(50, ge=1, le=200)):
    root = _repo(repository_id)
    base = (root / "results" / "runs").resolve()
    if not base.is_dir():
        return {"runs": []}
    found = []
    for folder in sorted(base.iterdir(), key=lambda p: p.name, reverse=True):
        if len(found) >= limit:
            break
        if folder.is_symlink() or not folder.is_dir() or folder.resolve().parent != base:
            continue
        marker = folder / "flbv3-run.json"
        if not marker.is_file() or marker.is_symlink() or marker.stat().st_size > 1_000_000:
            continue
        try:
            data = json.loads(marker.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        found.append({"run_id": folder.name, "state": data.get("state"),
                      "started_at": data.get("started_at"),
                      "finished_at": data.get("finished_at"),
                      "planned": len(data.get("planned_keys", [])) if isinstance(data.get("planned_keys"), list) else 0})
    return {"runs": found}
