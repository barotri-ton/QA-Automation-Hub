from pathlib import Path
import sys

from app.execution_groups import CaseInstance, CaseStatus, ExecutionGroup, SequentialRun
from app.local_runner import junit_status, run_sequential


def test_junit_outcomes(tmp_path: Path):
    xml = tmp_path / "result.xml"
    xml.write_text('<testsuite><testcase name="ok"/></testsuite>', encoding="utf-8")
    assert junit_status(xml, 0) == CaseStatus.PASSED
    xml.write_text('<testsuite><testcase name="bad"><failure/></testcase></testsuite>', encoding="utf-8")
    assert junit_status(xml, 1) == CaseStatus.FAILED
    xml.write_text('<testsuite><testcase name="skip"><skipped/></testcase></testsuite>', encoding="utf-8")
    assert junit_status(xml, 0) == CaseStatus.SKIPPED
    xml.write_text('<testsuite><testcase name="oops"><error/></testcase></testsuite>', encoding="utf-8")
    assert junit_status(xml, 1) == CaseStatus.ERROR
    assert junit_status(tmp_path / "missing.xml", 0) == CaseStatus.ERROR


def test_sequential_runner_updates_group_progress(tmp_path: Path):
    (tmp_path / "test_example.py").write_text(
        "def test_pass():\n    assert True\n"
        "def test_fail():\n    assert False\n", encoding="utf-8"
    )
    a = ExecutionGroup("NJM-1100", [CaseInstance("NJM-101", "test_example.py::test_pass")])
    b = ExecutionGroup("NJM-1200", [
        CaseInstance("NJM-102", "test_example.py::test_fail"),
        CaseInstance("NJM-103", None),
    ])
    run = SequentialRun("NJM-1000", [a, b])
    events = []
    run_sequential(
        run, tmp_path, python_executable=sys.executable,
        on_update=lambda state: events.append(
            [(g.jira_key, g.status) for g in state.groups]
        ),
    )
    assert a.status == "COMPLETED"
    assert b.status == "COMPLETED_WITH_FAILURES"
    assert b.cases[1].status == CaseStatus.MISSING_AUTOMATION
    assert run.summary()["completed"] == 2
    assert run.summary()["missing_automation"] == 1
    assert events[0][0] == ("NJM-1100", "RUNNING")
    assert events[0][1] == ("NJM-1200", "QUEUED")
    assert events[-1][1] == ("NJM-1200", "COMPLETED_WITH_FAILURES")


def test_runner_does_not_start_after_cancel(tmp_path: Path):
    (tmp_path / "test_example.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    group = ExecutionGroup("NJM-1100", [CaseInstance("NJM-101", "test_example.py::test_ok")])
    run = SequentialRun("NJM-1000", [group])
    run.cancel()
    run_sequential(run, tmp_path)
    assert group.cases[0].status == CaseStatus.CANCELLED
