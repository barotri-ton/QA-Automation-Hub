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
    assert result["counts_are_provisional"] is True
    assert result["provisional_count"] == 1
    assert result["verified_counts"]["PASSED"] == 0


def test_allure_evidence_metadata_is_scoped_to_matching_case(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "run-1"
    allure = run / "allure-results"
    allure.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (run / "junit-wave.xml").write_text('<testsuite><testcase name="test_njm_123"><failure message="Assertion failed"/></testcase></testsuite>')
    (allure / "image.png").write_bytes(b"test-image")
    (allure / "abc-result.json").write_text(json.dumps({
        "uuid": "abc", "name": "test_njm_123", "status": "failed", "start": 10, "stop": 20,
        "attachments": [
            {"name": "Failure screenshot", "source": "image.png", "type": "image/png"},
            {"name": "Unsafe", "source": "../private.txt", "type": "text/plain"},
            {"name": "Missing", "source": "missing.png", "type": "image/png"}
        ]
    }))
    result = analyze(root, run.name)
    case = result["cases"][0]
    assert case["evidence_count"] == 1
    assert case["allure_results"][0]["attachments"][0]["name"] == "Failure screenshot"
    assert result["allure_cases_with_evidence"] == 1
    assert case["final_verdict_verified"] is False


def test_allure_timeline_is_timestamp_ordered_but_not_final_verdict(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "run-2"
    allure = run / "allure-results"
    allure.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (run / "junit-wave.xml").write_text('<testsuite><testcase name="NJM-123"/></testsuite>')
    for name, start, status in [("a", 200, "passed"), ("b", 100, "failed")]:
        (allure / f"{name}-result.json").write_text(json.dumps({
            "name": "NJM-123", "start": start, "stop": start + 5, "status": status
        }))
    case = analyze(root, run.name)["cases"][0]
    assert [x["status"] for x in case["allure_timeline"]] == ["failed", "passed"]
    assert case["allure_timed_attempts"] == 2
    assert case["allure_timeline_confidence"] == "TIMESTAMPS_PRESENT_NOT_VERIFIED"
    assert case["final_verdict_verified"] is False


def test_reconciliation_detects_missing_and_mismatched_allure(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "run-3"
    allure = run / "allure-results"
    allure.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (run / "junit-wave.xml").write_text('<testsuite><testcase name="NJM-123"><failure message="failed"/></testcase></testsuite>')
    def state():
        return analyze(root, run.name)["cases"][0]["reconciliation"]["state"]
    assert state() == "ALLURE_MISSING"
    (allure / "a-result.json").write_text(json.dumps({"name": "NJM-123", "status": "passed"}))
    assert state() == "STATUS_DISTRIBUTION_MISMATCH"
    (allure / "a-result.json").write_text(json.dumps({"name": "NJM-123", "status": "failed"}))
    assert state() == "STATUS_COUNTS_MATCH_ORDER_UNVERIFIED"
    (allure / "b-result.json").write_text(json.dumps({"name": "NJM-123", "status": "failed"}))
    assert state() == "ATTEMPT_COUNT_MISMATCH"


def test_malformed_allure_collections_do_not_break_analysis(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "run-malformed"
    allure = run / "allure-results"
    allure.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (run / "junit-wave.xml").write_text('<testsuite><testcase name="NJM-123"/></testsuite>')
    (allure / "bad-result.json").write_text(json.dumps({
        "name": "NJM-123", "status": "passed", "labels": None, "attachments": {"bad": "shape"}
    }))
    case = analyze(root, run.name)["cases"][0]
    assert case["evidence_count"] == 0
    assert case["reconciliation"]["state"] == "STATUS_COUNTS_MATCH_ORDER_UNVERIFIED"


def test_junit_symlink_directory_cannot_escape_run_folder(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "run-safe"
    run.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "junit-secret.xml").write_text('<testsuite><testcase name="NJM-999"/></testsuite>')
    try:
        (run / "junit-external").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        return  # Windows without symlink privileges
    result = analyze(root, run.name)
    assert result["attempts"] == 0


def test_allure_only_case_is_visible_but_unverified(tmp_path):
    root = tmp_path / "automation"
    run = root / "results" / "runs" / "allure-only"
    allure = run / "allure-results"
    allure.mkdir(parents=True)
    (run / "flbv3-run.json").write_text("{}")
    (allure / "orphan-result.json").write_text(json.dumps({
        "name": "test_NJM-777", "status": "failed", "start": 100, "stop": 110
    }))
    result = analyze(root, run.name)
    assert result["attempts"] == 0
    assert result["counts"]["UNKNOWN"] == 1
    case = result["cases"][0]
    assert case["key"] == "NJM-777"
    assert case["status"] == "UNKNOWN"
    assert case["reconciliation"]["state"] == "JUNIT_MISSING"
    assert case["needs_verdict_review"] is True
    assert case["final_verdict_verified"] is False
