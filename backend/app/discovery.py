"""Pytest collection runs in a subprocess; no test functions are executed.

Collection imports test modules and executes conftest/plugin hooks, so only scan
trusted, explicitly registered directories. Never expose this API publicly.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

JIRA_KEY = re.compile(r"(?<![A-Z0-9])NJM-\d+(?![A-Z0-9])", re.I)
PLUGIN = '''import json, os, pytest

def pytest_collection_finish(session):
    result=[]
    for item in session.items:
        markers=[{"name": m.name, "args": [str(a) for a in m.args]} for m in item.iter_markers()]
        result.append({"nodeid": item.nodeid, "markers": markers})
    with open(os.environ["QA_HUB_COLLECTION_OUTPUT"], "w", encoding="utf-8") as f:
        json.dump(result, f)
'''

class CollectionError(RuntimeError):
    pass


def collect_tests(path: Path, timeout: int = 90, python_executable: str | None = None) -> list[dict]:
    interpreter = python_executable or sys.executable
    if not Path(interpreter).is_file():
        raise CollectionError("Configured Python interpreter does not exist")
    with tempfile.TemporaryDirectory(prefix="qa-hub-") as temp:
        plugin = Path(temp) / "hub_collection_plugin.py"
        output = Path(temp) / "collected.json"
        plugin.write_text(PLUGIN, encoding="utf-8")
        env = dict(os.environ)
        env["QA_HUB_COLLECTION_OUTPUT"] = str(output)
        env["PYTHONPATH"] = os.pathsep.join([temp, str(path), env.get("PYTHONPATH", "")])
        try:
            proc = subprocess.run([interpreter, "-m", "pytest", "--collect-only", "-q", "-p", "hub_collection_plugin"], cwd=path, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise CollectionError(f"Pytest collection timed out after {timeout} seconds") from exc
        except OSError as exc:
            raise CollectionError("Could not start configured Python interpreter") from exc
        if proc.returncode not in (0, 5) or not output.exists():
            raise CollectionError(f"Pytest collection failed (exit {proc.returncode}); check the repository environment and local runner logs")
        results = json.loads(output.read_text(encoding="utf-8"))
        for item in results:
            values = [str(a) for marker in item["markers"] for a in marker["args"]]
            values += [marker["name"] for marker in item["markers"]]
            keys = sorted({m.upper() for value in values for m in JIRA_KEY.findall(value)})
            item["jira_keys"] = keys
        return results
