"""Offline manual spec check API contract tests."""
from fastapi import HTTPException
from pydantic import ValidationError
from app.spec_checks import SpecCheckInput, save, get_check, list_checks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base


def test_spec_marker_round_trip():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        payload = SpecCheckInput(run_id="demo-run", test_key="NJM-123", status="VERIFIED",
                                 reviewer="QA", note="Checked current spec manually")
        result = save(payload, db=db)
        assert result["status"] == "VERIFIED"
        assert result["manual_only"] is True
        assert get_check("demo-run", "NJM-123", db=db)["note"] == payload.note
        assert len(list_checks("demo-run", db=db)) == 1
        payload.status = "NEEDS_UPDATE"
        save(payload, db=db)
        assert len(list_checks("demo-run", db=db)) == 1


def test_invalid_status_rejected():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        try:
            save(SpecCheckInput(run_id="run", test_key="NJM-123", status="AUTO_VERIFIED", reviewer="QA"), db=db)
        except HTTPException as exc:
            assert exc.status_code == 422
        else:
            raise AssertionError("Invalid status accepted")
