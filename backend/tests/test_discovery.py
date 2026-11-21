from pathlib import Path
import pytest
from app.discovery import collect_tests


def test_collect_jira_markers_without_executing_tests(tmp_path: Path):
    (tmp_path / "pytest.ini").write_text("[pytest]\\nmarkers = jira(key): Jira test case\\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(
        "import pytest\\n"
        "@pytest.mark.jira('NJM-1234')\\n"
        "def test_mapped():\\n    assert True\\n"
        "def test_unmapped():\\n    assert True\\n", encoding="utf-8"
    )
    items = collect_tests(tmp_path)
    by_name = {x["nodeid"]: x for x in items}
    assert by_name["test_sample.py::test_mapped"]["jira_keys"] == ["NJM-1234"]
    assert by_name["test_sample.py::test_unmapped"]["jira_keys"] == []


def test_collect_does_not_run_test_body(tmp_path: Path):
    (tmp_path / "test_no_run.py").write_text(
        "def test_never_execute():\\n    raise AssertionError('body executed')\\n", encoding="utf-8"
    )
    items = collect_tests(tmp_path)
    assert len(items) == 1


def test_collect_reports_multiple_mappings(tmp_path: Path):
    (tmp_path / "pytest.ini").write_text("[pytest]\\nmarkers = jira(key): Jira test case\\n", encoding="utf-8")
    (tmp_path / "test_multi.py").write_text(
        "import pytest\\n"
        "@pytest.mark.jira('NJM-101', 'NJM-102')\\n"
        "def test_multi():\\n    pass\\n", encoding="utf-8"
    )
    assert collect_tests(tmp_path)[0]["jira_keys"] == ["NJM-101", "NJM-102"]
