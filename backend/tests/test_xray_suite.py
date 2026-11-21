import pytest

from app.execution_groups import CaseStatus
from app.xray_suite import (
    SuiteSelection, XrayCase, XrayExecution, XrayPlanSnapshot,
    build_sequential_run, review_plan,
)


def sample_plan():
    return XrayPlanSnapshot(
        "NJM-1000",
        (
            XrayExecution("NJM-1100", (
                XrayCase("NJM-101", "Login"),
                XrayCase("NJM-102", "Backup"),
            )),
            XrayExecution("NJM-1200", (
                XrayCase("NJM-101", "Login again"),
                XrayCase("NJM-201", "Restore"),
            )),
        ),
    )


def test_review_tree_preserves_execution_membership():
    tree = review_plan(sample_plan(), {"NJM-101": "test_login.py::test_login"})
    assert len(tree["executions"]) == 2
    assert tree["executions"][0]["cases"][0]["automation_status"] == "AUTOMATED"
    assert tree["executions"][0]["cases"][1]["automation_status"] == "MISSING_AUTOMATION"


def test_suite_selection_keeps_duplicate_case_instances():
    plan = sample_plan()
    suite = SuiteSelection({
        "NJM-1100": frozenset({"NJM-101"}),
        "NJM-1200": frozenset({"NJM-101", "NJM-201"}),
    })
    run = build_sequential_run(
        plan, suite, {"NJM-101": "test_login.py::test_login"}
    )
    assert run.summary()["total"] == 2
    assert run.summary()["missing_automation"] == 1
    assert run.groups[0].cases[0].id != run.groups[1].cases[0].id
    group_id, case_id = run.start_next()
    assert group_id == run.groups[0].id
    run.finish(group_id, case_id, CaseStatus.PASSED)
    assert run.active_group().id == run.groups[1].id


def test_excluded_case_not_counted():
    run = build_sequential_run(
        sample_plan(),
        SuiteSelection({"NJM-1100": frozenset({"NJM-101"})}),
        {"NJM-101": "test_login.py::test_login"},
    )
    assert run.summary()["total"] == 1
    assert run.summary()["missing_automation"] == 0
    assert len(run.groups) == 1


def test_reject_unknown_case_and_empty_suite():
    with pytest.raises(ValueError, match="Unknown cases"):
        build_sequential_run(
            sample_plan(),
            SuiteSelection({"NJM-1100": frozenset({"NJM-999"})}),
            {},
        )
    with pytest.raises(ValueError, match="at least one"):
        build_sequential_run(sample_plan(), SuiteSelection({}), {})


def test_reject_duplicate_case_in_same_execution():
    with pytest.raises(ValueError, match="Duplicate case"):
        XrayPlanSnapshot(
            "NJM-1000",
            (XrayExecution("NJM-1100", (
                XrayCase("NJM-101"), XrayCase("NJM-101")
            )),),
        )
