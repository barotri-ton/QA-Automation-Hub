import pytest

from app.execution_groups import (
    CaseInstance, CaseStatus, ExecutionGroup, SequentialRun,
)


def test_execution_groups_run_sequentially():
    first = ExecutionGroup("NJM-1100", [
        CaseInstance("NJM-101", "test_a.py::test_a"),
        CaseInstance("NJM-102", "test_b.py::test_b"),
    ])
    second = ExecutionGroup("NJM-1200", [
        CaseInstance("NJM-201", "test_c.py::test_c"),
    ])
    run = SequentialRun("NJM-1000", [first, second])
    group_id, case_id = run.start_next()
    assert group_id == first.id
    assert run.start_next() is None  # never overlap cases
    run.finish(group_id, case_id, CaseStatus.PASSED)
    assert run.active_group().id == first.id
    group_id, case_id = run.start_next()
    run.finish(group_id, case_id, CaseStatus.FAILED)
    assert first.status == "COMPLETED_WITH_FAILURES"
    assert run.active_group().id == second.id
    assert second.status == "QUEUED"
    group_id, case_id = run.start_next()
    assert group_id == second.id
    assert second.status == "RUNNING"
    run.finish(group_id, case_id, CaseStatus.PASSED)
    assert second.status == "COMPLETED"
    assert run.summary()["completed"] == 3


def test_duplicate_jira_case_is_distinct_per_execution():
    a = ExecutionGroup("NJM-1100", [CaseInstance("NJM-101", "test_a.py::test_a")])
    b = ExecutionGroup("NJM-1200", [CaseInstance("NJM-101", "test_a.py::test_a")])
    run = SequentialRun("NJM-1000", [a, b])
    assert a.cases[0].id != b.cases[0].id
    assert run.summary()["total"] == 2


def test_missing_automation_is_not_failure_or_completed():
    blocked = ExecutionGroup("NJM-1100", [CaseInstance("NJM-101", None)])
    run = SequentialRun("NJM-1000", [blocked])
    assert blocked.status == "BLOCKED"
    assert run.summary()["total"] == 0
    assert run.summary()["missing_automation"] == 1
    assert run.start_next() is None


def test_cancel_preserves_missing_and_terminates_queued():
    group = ExecutionGroup("NJM-1100", [
        CaseInstance("NJM-101", "test_a.py::test_a"),
        CaseInstance("NJM-102", None),
    ])
    run = SequentialRun("NJM-1000", [group])
    run.start_next()
    run.cancel()
    assert run.start_next() is None
    assert group.cases[0].status == CaseStatus.CANCELLED
    assert group.cases[1].status == CaseStatus.MISSING_AUTOMATION


def test_reject_finishing_non_running_case():
    group = ExecutionGroup("NJM-1100", [CaseInstance("NJM-101", "test_a.py::test_a")])
    run = SequentialRun("NJM-1000", [group])
    with pytest.raises(ValueError):
        run.finish(group.id, group.cases[0].id, CaseStatus.PASSED)
