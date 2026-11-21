from pathlib import Path

import pytest

from app.discovery import CollectionError, collect_tests


def test_collection_failure_does_not_expose_fixture_output(tmp_path: Path):
    (tmp_path / "test_broken.py").write_text(
        "raise RuntimeError('secret fixture value')\n", encoding="utf-8"
    )
    with pytest.raises(CollectionError, match="collection failed") as error:
        collect_tests(tmp_path)
    assert "secret fixture value" not in str(error.value)


def test_invalid_interpreter_rejected(tmp_path: Path):
    with pytest.raises(CollectionError, match="does not exist"):
        collect_tests(tmp_path, python_executable=str(tmp_path / "missing-python"))


def test_reject_partial_jira_key(tmp_path: Path):
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers = jira(key): Jira test case\n", encoding="utf-8"
    )
    (tmp_path / "test_keys.py").write_text(
        "import pytest\n"
        "@pytest.mark.jira('NJM-1234X')\n"
        "def test_invalid():\n    pass\n"
        "@pytest.mark.jira('NJM-1234')\n"
        "def test_valid():\n    pass\n", encoding="utf-8"
    )
    items = {x["nodeid"]: x for x in collect_tests(tmp_path)}
    assert items["test_keys.py::test_invalid"]["jira_keys"] == []
    assert items["test_keys.py::test_valid"]["jira_keys"] == ["NJM-1234"]
