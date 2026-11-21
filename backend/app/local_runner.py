"""Sequential Pytest runner for trusted local automation repositories.

Executes exactly one pytest node ID at a time, preserving Xray execution
group boundaries. Never modifies test source intentionally; pytest plugins
and test code themselves may write files, so run only trusted projects.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable

from .execution_groups import CaseStatus, SequentialRun


def junit_status(path: Path, returncode: int) -> CaseStatus:
    """Prefer JUnit outcome over process exit code, which may be shared."""
    if not path.is_file():
        return CaseStatus.ERROR
    try:
        root = ET.parse(path).getroot()
        cases = root.findall(".//testcase")
        if len(cases) != 1:
            return CaseStatus.ERROR
        case = cases[0]
        if case.find("error") is not None:
            return CaseStatus.ERROR
        if case.find("failure") is not None:
            return CaseStatus.FAILED
        if case.find("skipped") is not None:
            return CaseStatus.SKIPPED
        return CaseStatus.PASSED if returncode == 0 else CaseStatus.ERROR
    except (ET.ParseError, OSError):
        return CaseStatus.ERROR


def run_sequential(
    run: SequentialRun,
    repository_path: Path,
    *,
    python_executable: str | None = None,
    timeout_seconds: int = 900,
    on_update: Callable[[SequentialRun], None] | None = None,
) -> SequentialRun:
    """Run synchronously; caller should use a worker thread/process.

    on_update is called when a case starts and after it finishes. Callers
    should persist each update before displaying progress.
    """
    root = repository_path.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Automation repository directory does not exist")
    interpreter = python_executable or sys.executable
    if not Path(interpreter).is_file():
        raise ValueError("Python interpreter does not exist")
    if timeout_seconds < 1:
        raise ValueError("Timeout must be positive")

    while not run.cancelled:
        item = run.next_case()
        if item is None:
            break
        group, case = item
        run.start_next()
        if on_update:
            on_update(run)
        with tempfile.TemporaryDirectory(prefix="qa-hub-run-") as temp:
            junit = Path(temp) / "result.xml"
            env = dict(os.environ)
            # Reduce incidental source-tree writes; third-party plugins or
            # test code may still write to their own working directories.
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            try:
                result = subprocess.run(
                    [
                        interpreter, "-m", "pytest",
                        case.nodeid, "-q", "-p", "no:cacheprovider",
                        f"--junitxml={junit}",
                    ],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                outcome = junit_status(junit, result.returncode)
            except (subprocess.TimeoutExpired, OSError):
                outcome = CaseStatus.ERROR
        run.finish(group.id, case.id, outcome)
        if on_update:
            on_update(run)
    return run
