# QA Automation Hub — Local UAT handoff

## Scope
Backend FastAPI/SQLite, React/Vite frontend, Jira Server/DC Xray Raven read-only import, sequential Xray suites, FLBv3 PowerShell wave/retry runner, event monitor, JUnit result review and local failure classification.

## Start (Windows, trusted loopback only)
See [LOCAL_WINDOWS_TEST.md](LOCAL_WINDOWS_TEST.md). Configure `QA_HUB_JIRA_PAT` in backend environment; never commit it. Register the **local folder** containing existing `flb-automation` scripts. The Hub never edits those scripts.

## Before using destructive automation
- Run on an isolated VM/lab. Existing PowerShell preflight can pull Git, seed fixtures and clean up AUTO_FLB jobs.
- Only enable gated categories after reviewing their impact. Wave 9 is license-sensitive and must not be automatically retried.
- The backend has no login/authorization: bind strictly to `127.0.0.1`, do not expose Vite/backend to a network, use one uvicorn worker.
- Jira result publishing is intentionally disabled; status updates and evidence uploads require a separate, audited approval workflow.

## Known gaps / acceptance blockers
- No Windows VM or live Jira integration test performed here; deployment behavior is unverified.
- Runner locking is process-local; restart recovery and cross-process arbitration are incomplete.
- JUnit aggregation is best-effort; a filename-ordered last result is **not** proof of the chronologically final retry. Inspect Allure history before declaring final status.
- Jira custom fields are instance-specific; current test detail API still uses known field IDs.
- Imported Test Run IDs persist in suite JSON snapshots but are not attached to the sequential runner's case instance model.
- No automatic spec comparison or product-bug determination; reviews are human decisions.
- No Jira publishing UI/backend. Do not claim results were synced.
- Frontend and backend compilation/test suite must be run on the target development machine before acceptance.

## Suggested local checks
```powershell
cd backend
python -m pytest -q
cd ..\frontend
npm ci
npm run build
```
Then perform manual Jira import and wave smoke tests in a safe lab. Track failures as issues before production use.
