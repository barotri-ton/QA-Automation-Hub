"""Xray import snapshot and suite selection domain models.

This module does not call Jira. Xray adapters must populate the snapshot from
verified Server/Data Center APIs and keep credentials server-side.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .execution_groups import CaseInstance, ExecutionGroup, SequentialRun


@dataclass(frozen=True)
class XrayCase:
    jira_key: str
    summary: str = ""


@dataclass(frozen=True)
class XrayExecution:
    jira_key: str
    cases: tuple[XrayCase, ...]
    summary: str = ""


@dataclass(frozen=True)
class XrayPlanSnapshot:
    jira_key: str
    executions: tuple[XrayExecution, ...]
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    revision: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self):
        keys = [execution.jira_key for execution in self.executions]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate execution key in Xray snapshot")
        for execution in self.executions:
            case_keys = [case.jira_key for case in execution.cases]
            if len(case_keys) != len(set(case_keys)):
                raise ValueError(
                    f"Duplicate case within execution {execution.jira_key}"
                )


@dataclass(frozen=True)
class SuiteSelection:
    """Selected membership is execution-scoped, never globally deduplicated."""

    selected: dict[str, frozenset[str]]
    revision: str = field(default_factory=lambda: str(uuid4()))


def review_plan(
    snapshot: XrayPlanSnapshot,
    mappings: dict[str, str],
) -> dict:
    """Return a read-only review tree; mappings are Jira key -> pytest node ID."""
    return {
        "plan_key": snapshot.jira_key,
        "snapshot_revision": snapshot.revision,
        "fetched_at": snapshot.fetched_at.isoformat(),
        "executions": [
            {
                "execution_key": execution.jira_key,
                "summary": execution.summary,
                "cases": [
                    {
                        "jira_key": case.jira_key,
                        "summary": case.summary,
                        "nodeid": mappings.get(case.jira_key),
                        "automation_status": (
                            "AUTOMATED" if mappings.get(case.jira_key)
                            else "MISSING_AUTOMATION"
                        ),
                    }
                    for case in execution.cases
                ],
            }
            for execution in snapshot.executions
        ],
    }


def build_sequential_run(
    snapshot: XrayPlanSnapshot,
    selection: SuiteSelection,
    mappings: dict[str, str],
) -> SequentialRun:
    known = {
        execution.jira_key: {case.jira_key for case in execution.cases}
        for execution in snapshot.executions
    }
    for execution_key, case_keys in selection.selected.items():
        if execution_key not in known:
            raise ValueError(f"Unknown execution: {execution_key}")
        unknown = case_keys - known[execution_key]
        if unknown:
            raise ValueError(
                f"Unknown cases in {execution_key}: {', '.join(sorted(unknown))}"
            )

    groups = [
        ExecutionGroup(
            jira_key=execution.jira_key,
            cases=[
                CaseInstance(
                    jira_key=case.jira_key,
                    nodeid=mappings.get(case.jira_key),
                )
                for case in execution.cases
                if case.jira_key in selection.selected.get(
                    execution.jira_key, frozenset()
                )
            ],
        )
        for execution in snapshot.executions
        if execution.jira_key in selection.selected
    ]
    if not groups or not any(group.cases for group in groups):
        raise ValueError("Suite must contain at least one selected test case")
    return SequentialRun(plan_key=snapshot.jira_key, groups=groups)
