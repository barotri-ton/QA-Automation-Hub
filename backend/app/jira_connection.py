"""Loopback-only, process-memory Jira PAT configuration.

Never stores PAT on disk, sends it to frontend, or exposes it in logs.
Single-process local Windows backend only. Set env vars for durable config.
"""
import os
import threading
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/jira/connection", tags=["Jira connection"])
_lock = threading.RLock()
_runtime_pat = None
_runtime_url = None


class ConnectionInput(BaseModel):
    base_url: str = Field(min_length=10, max_length=512)
    pat: str = Field(min_length=1, max_length=4096)


def _local(request: Request):
    host = request.client.host if request.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(403, "Jira credentials may only be configured through a local backend")
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.scheme not in ("http", "https"):
            raise HTTPException(403, "Untrusted origin")


def _validate_url(value: str):
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422, "Invalid Jira base URL")
    return value.rstrip("/")


def effective_credentials():
    with _lock:
        return (_runtime_url or os.getenv("QA_HUB_JIRA_BASE_URL", "http://10.170.180.181:8080"),
                _runtime_pat or os.getenv("QA_HUB_JIRA_PAT", ""))


@router.get("")
def get_connection(request: Request):
    _local(request)
    url, token = effective_credentials()
    return {"base_url": url, "configured": bool(token), "source": "runtime" if _runtime_pat else "environment" if token else "none",
            "pat": None, "storage": "process_memory_only"}


@router.put("")
def set_connection(payload: ConnectionInput, request: Request):
    _local(request)
    url = _validate_url(payload.base_url)
    global _runtime_pat, _runtime_url
    with _lock:
        _runtime_url, _runtime_pat = url, payload.pat
    return {"base_url": url, "configured": True, "source": "runtime", "pat": None, "storage": "process_memory_only"}


@router.delete("")
def clear_connection(request: Request):
    _local(request)
    global _runtime_pat, _runtime_url
    with _lock:
        _runtime_pat, _runtime_url = None, None
    return {"configured": bool(os.getenv("QA_HUB_JIRA_PAT")), "source": "environment" if os.getenv("QA_HUB_JIRA_PAT") else "none", "pat": None}


@router.post("/test")
def test_connection(request: Request):
    _local(request)
    url, token = effective_credentials()
    if not token:
        raise HTTPException(503, "Configure a Jira PAT first")
    try:
        with httpx.Client(base_url=_validate_url(url), headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}, timeout=10, follow_redirects=False) as client:
            response = client.get("/rest/api/2/myself")
        if response.status_code != 200:
            return {"connected": False, "http_status": response.status_code, "message": "Jira rejected connection or credentials"}
        data = response.json()
        return {"connected": True, "display_name": data.get("displayName"), "username": data.get("name")}
    except (httpx.RequestError, ValueError):
        return {"connected": False, "message": "Cannot reach Jira or parse response"}
