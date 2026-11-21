"""Offline manual spec check API contract tests."""
from fastapi import HTTPException
from app.spec_checks import SpecCheckInput, save, get_check, list_checks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base


def test_spec_marker_round_trip(monkeypatch):
    from app import flbv3_results, flbv3_runner_api
    monkeypatch.setattr(flbv3_runner_api, "_repo", lambda _: "/fixture")
    monkeypatch.setattr(flbv3_results, "analyze", lambda root, run: {"cases": [{"key": "NJM-123", "status": "FAILED"}]})
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = SpecCheckInput(repository_id=1, run_id="demo-run", test_key="NJM-123", status="VERIFIED", failed_reason_unclear=True,
                                 reviewer="QA", note="Checked current spec manually")
        result = save(payload, db=db)
        assert result["status"] == "VERIFIED"
        assert result["manual_only"] is True
        assert get_check("demo-run", "NJM-123", db=db)["note"] == payload.note
        assert len(list_checks("demo-run", db=db)) == 1
        payload.status = "NEEDS_UPDATE"
        save(payload, db=db)
        assert len(list_checks("demo-run", db=db)) == 1


def test_invalid_status_rejected(monkeypatch):
    from app import flbv3_results, flbv3_runner_api
    monkeypatch.setattr(flbv3_runner_api, "_repo", lambda _: "/fixture")
    monkeypatch.setattr(flbv3_results, "analyze", lambda root, run: {"cases": [{"key": "NJM-123", "status": "FAILED"}]})
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        try:
            save(SpecCheckInput(run_id="run", test_key="NJM-123", status="AUTO_VERIFIED", failed_reason_unclear=True, reviewer="QA"), db=db)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Invalid status accepted")


def test_passed_case_cannot_be_marked(monkeypatch):
    from app import flbv3_results, flbv3_runner_api
    monkeypatch.setattr(flbv3_runner_api, "_repo", lambda _: "/fixture")
    monkeypatch.setattr(flbv3_results, "analyze", lambda root, run: {"cases": [{"key": "NJM-123", "status": "PASSED"}]})
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = SpecCheckInput(repository_id=1, run_id="run", test_key="NJM-123", status="VERIFIED", failed_reason_unclear=True, reviewer="QA")
        try:
            save(payload, db=db)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("PASSED case incorrectly eligible for spec verification")
