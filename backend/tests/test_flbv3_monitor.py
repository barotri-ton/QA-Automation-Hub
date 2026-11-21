import json
from pathlib import Path

import pytest
from app.flbv3_monitor import read_monitor


def make_run(tmp_path):
    folder = tmp_path / "results" / "runs" / "20261121-120000"
    events = folder / "allure-results" / "runner-events"
    events.mkdir(parents=True)
    (folder / "flbv3-run.json").write_text(json.dumps({
        "state": "RUNNING", "planned_keys": ["NJM-101", "NJM-102"]
    }), encoding="utf-8")
    return folder, events


def test_live_events_and_partial_line(tmp_path):
    folder, events = make_run(tmp_path)
    (events / "wave-host-1.jsonl").write_text("\n".join([
        json.dumps({"event": "file_started", "ts": 1, "key": "NJM-101", "child_pid": 123}),
        "{partial",
        json.dumps({"event": "file_finished", "ts": 2, "key": "NJM-101", "exit": 1}),
        json.dumps({"event": "file_started", "ts": 3, "key": "NJM-102", "child_pid": 456}),
    ]), encoding="utf-8")
    result = read_monitor(tmp_path, folder.name)
    cases = {c["key"]: c for c in result["cases"]}
    assert cases["NJM-101"]["status"] == "FAILED"
    assert cases["NJM-102"]["status"] == "RUNNING"
    assert result["active_workers"][0]["pid"] == 456
    assert result["event_count"] == 3


def test_missing_events_are_not_failures(tmp_path):
    folder, _ = make_run(tmp_path)
    result = read_monitor(tmp_path, folder.name)
    assert all(case["status"] == "PLANNED" for case in result["cases"])


@pytest.mark.parametrize("bad", ["../escape", ".", "..", "x/y", "x\\\\y"])
def test_rejects_path_traversal(tmp_path, bad):
    with pytest.raises(ValueError):
        read_monitor(tmp_path, bad)
