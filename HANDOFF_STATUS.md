# QA Automation Hub — Local UAT handoff

## Scope
Backend FastAPI/SQLite, React/Vite frontend, Jira Server/DC Xray Raven read-only import, sequential Xray suites, FLBv3 PowerShell wave/retry runner, event monitor, JUnit result review and local failure classification.

## Start (Windows, trusted loopback only)
See [LOCAL_WINDOWS_TEST.md](LOCAL_WINDOWS_TEST.md). Configure the Jira PAT in the local **Settings · Jira Connection** UI (process memory only), or use `QA_HUB_JIRA_PAT` in the backend environment; never commit it. Register the **local folder** containing existing `flb-automation` scripts. The Hub never edits those scripts.

## Before using destructive automation
- Run on an isolated VM/lab. Existing PowerShell preflight can pull Git, seed fixtures and clean up AUTO_FLB jobs.
- Only enable gated categories after reviewing their impact. Wave 9 is license-sensitive and must not be automatically retried.
- The backend has no login/authorization: bind strictly to `127.0.0.1`, do not expose Vite/backend to a network, use one uvicorn worker.
- Jira result publishing is intentionally disabled; status updates and evidence uploads require a separate, audited approval workflow.

## Known gaps / acceptance blockers
- Backend stale spec-reference import fixed in `investigations.py`; regression test now imports the complete FastAPI app. **Unit tests and frontend build have not yet been executed**, and Windows VM / live Jira integration remains unverified.
- Runner locking is process-local; restart recovery and cross-process arbitration are incomplete.
- Allure result metadata is indexed per NJM case from local `allure-results/*-result.json` (bounded read, safe attachment names, existence checks). UI shows evidence inventory only; no binary attachment endpoint and Allure timestamp-based attempt timeline is visible for manual reconciliation, and JUnit/Allure attempt counts and status distributions are cross-checked per TC. A match does not prove attempt identity, retry order or final verdict.
- JUnit aggregation is best-effort; file-mtime ordering is **not** proof of the chronologically final retry. Results now expose `retry_conflict`, `needs_verdict_review`, and `final_verdict_verified=false`; the dashboard flags unresolved retries. Inspect Allure history before declaring final status.
- FLBv3 monitor NJM key regex has been corrected; offline regression coverage includes planned keys and retry events. This does **not** establish live Windows validation.
- Jira custom fields are instance-specific; current test detail API still uses known field IDs.
- Imported Test Run IDs persist in suite JSON snapshots but are not attached to the sequential runner's case instance model.
- No automatic spec comparison or product-bug determination; reviews are human decisions.
- No Jira publishing UI/backend. Do not claim results were synced.
- Frontend and backend compilation/test suite must be run on the target development machine before acceptance.

- Allure parser now tolerates malformed `labels` / `attachments` collections; JUnit candidate paths must resolve inside the selected run folder, preventing symlink-directory escape. Offline regression tests were added but have not been executed in the target environment.
- Latest commit status endpoint reported Vercel success on `3f145df`; GitHub Actions results were not available through the PR-only workflow-run lookup. Do not treat Vercel success as backend pytest PASS.

## Suggested local checks
```powershell
cd backend
python -m pytest -q
cd ..\frontend
npm ci
npm run build
```
Then perform manual Jira import and wave smoke tests in a safe lab. Track failures as issues before production use.

## Evidence cross-check (new)
- Local backend endpoint: `GET /api/investigations/repositories/{repository_id}/runs/{run_id}/tests/{test_key}?test_run_id={xray_run_id}`.
- `test_run_id` is optional but should be provided from the selected Xray execution for execution-scoped evidence. The endpoint reads local JUnit and Jira/Xray only; it never writes to Jira.
- If Jira is unavailable, `jira_error` is populated and local runner evidence remains visible. `specification.state=NOT_CONNECTED` means no manual spec marker exists; QA verifies the specification manually only when a FAILED test has an unclear cause.
- In the local frontend, select a repository and run under FLBv3 Results, click Review Jira, enter the execution-specific Test Run ID and click Compare Jira + JUnit.
- This is an integration implementation, **not** verified against the real intranet Jira or Windows runner. The Vercel demo continues to use synthetic data.

- Allure-only NJM cases lacking JUnit are now surfaced as UNKNOWN / JUNIT_MISSING and flagged for review, never counted as confirmed FAILED/PASSED. Dashboard includes UNKNOWN filter. Added offline regression test; CI execution still pending verification.
