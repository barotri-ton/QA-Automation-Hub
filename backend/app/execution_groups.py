"""Sequential Xray Test Execution run state machine.

Pure domain model; actual Pytest subprocess scheduling and Jira import are separate.
No Jira write-back is performed.
"""
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class CaseStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    MISSING_AUTOMATION = "MISSING_AUTOMATION"


TERMINAL = {
    CaseStatus.PASSED, CaseStatus.FAILED, CaseStatus.SKIPPED,
    CaseStatus.ERROR, CaseStatus.CANCELLED,
}


@dataclass
class CaseInstance:
    jira_key: str
    nodeid: str | None
    id: str = field(default_factory=lambda: str(uuid4()))
    status: CaseStatus = CaseStatus.QUEUED
    attempt: int = 0

    def __post_init__(self):
        if not self.nodeid:
            self.status = CaseStatus.MISSING_AUTOMATION


@dataclass
class ExecutionGroup:
    jira_key: str
    cases: list[CaseInstance]
    id: str = field(default_factory=lambda: str(uuid4()))

    @property
    def status(self) -> str:
        runnable = [c for c in self.cases if c.nodeid]
        if not runnable:
            return "BLOCKED"
        if any(c.status == CaseStatus.RUNNING for c in runnable):
            return "RUNNING"
        if all(c.status in TERMINAL for c in runnable):
            if any(c.status in {CaseStatus.FAILED, CaseStatus.ERROR} for c in runnable):
                return "COMPLETED_WITH_FAILURES"
            if all(c.status == CaseStatus.CANCELLED for c in runnable):
                return "CANCELLED"
            return "COMPLETED"
        if any(c.status in TERMINAL for c in runnable):
            return "RUNNING"
        return "QUEUED"

    def summary(self) -> dict:
        runnable = [c for c in self.cases if c.nodeid]
        return {
            "group_id": self.id,
            "execution_key": self.jira_key,
            "status": self.status,
            "total": len(runnable),
            "completed": sum(c.status in TERMINAL for c in runnable),
            "missing_automation": sum(not c.nodeid for c in self.cases),
            "passed": sum(c.status == CaseStatus.PASSED for c in runnable),
            "failed": sum(c.status == CaseStatus.FAILED for c in runnable),
            "running": sum(c.status == CaseStatus.RUNNING for c in runnable),
            "queued": sum(c.status == CaseStatus.QUEUED for c in runnable),
        }


@dataclass
class SequentialRun:
    plan_key: str
    groups: list[ExecutionGroup]
    id: str = field(default_factory=lambda: str(uuid4()))
    cancelled: bool = False

    def active_group(self) -> ExecutionGroup | None:
        """Only the first unfinished group can be scheduled."""
        if self.cancelled:
            return None
        for group in self.groups:
            if group.status in {"COMPLETED", "COMPLETED_WITH_FAILURES", "BLOCKED", "CANCELLED"}:
                continue
            return group
        return None

    def next_case(self) -> tuple[ExecutionGroup, CaseInstance] | None:
        group = self.active_group()
        if group is None:
            return None
        if any(c.status == CaseStatus.RUNNING for c in group.cases):
            return None
        for case in group.cases:
            if case.status == CaseStatus.QUEUED:
                return group, case
        return None

    def start_next(self) -> tuple[str, str] | None:
        next_item = self.next_case()
        if next_item is None:
            return None
        group, case = next_item
        case.status = CaseStatus.RUNNING
        case.attempt += 1
        return group.id, case.id

    def finish(self, group_id: str, case_id: str, result: CaseStatus) -> None:
        if result not in TERMINAL:
            raise ValueError("A case must finish with a terminal result")
        for group in self.groups:
            if group.id != group_id:
                continue
            for case in group.cases:
                if case.id == case_id:
                    if case.status != CaseStatus.RUNNING:
                        raise ValueError("Case is not running")
                    case.status = result
                    return
        raise KeyError("Unknown group or case instance")

    def cancel(self) -> None:
        self.cancelled = True
        for group in self.groups:
            for case in group.cases:
                if case.status in {CaseStatus.QUEUED, CaseStatus.RUNNING}:
                    case.status = CaseStatus.CANCELLED

    def summary(self) -> dict:
        groups = [g.summary() for g in self.groups]
        return {
            "run_id": self.id,
            "plan_key": self.plan_key,
            "cancelled": self.cancelled,
            "groups": groups,
            "total": sum(g["total"] for g in groups),
            "completed": sum(g["completed"] for g in groups),
            "missing_automation": sum(g["missing_automation"] for g in groups),
        }
