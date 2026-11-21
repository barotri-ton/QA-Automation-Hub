"""Offline FLBv3 inventory/results regression tests."""
import json
from pathlib import Path

from app.flbv3_inventory import list_runs
from app.flbv3_results import analyze


def test_inventory_discovers_only_marked_runs(tmp_path, monkeypatch):
    from app import flbv3_inventory
    root = tmp_path / "automation"
    good = root / "results" / "runs" / "20261121-120000"
    good.mkdir(parents=True)
    (good / "flbv3-run.json").write_text(json.dumps({"state": "FINISHED", "planned_keys": ["NJM-123"]}))
    (good.parent / "unrelated").mkdir()
    monkeypatch.setattr(flbv3_inventory, "_repo", lambda _: root)
    rows = list_runs(1, limit=50)
    assert len(rows["runs"]) == 1
    assert rows["runs"][0]["planned"] == 1


def test_results_preserve_retry_attempts(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "20261121-120000"
    run.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (run / "junit-wave1.xml").write_text(
        '<testsuite><testcase name="test_njm_123"><failure message="Assertion failed"/></testcase></testsuite>'
    )
    (run / "junit-retry.xml").write_text(
        '<testsuite><testcase name="test_njm_123"/></testsuite>'
    )
    result = analyze(root, run.name)
    assert result["attempts"] == 2
    assert result["cases"][0]["attempts"] == 2
    assert len(result["cases"][0]["history"]) == 1
    assert result["cases"][0]["verdict_confidence"] == "PROVISIONAL_FILE_MTIME"
    assert result["cases"][0]["retry_conflict"] is True
    assert result["cases"][0]["needs_verdict_review"] is True
    assert result["cases"][0]["final_verdict_verified"] is False
    assert result["conflicting_retry_outcomes"] == 1
