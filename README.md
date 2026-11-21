# QA Automation Hub

Local-first QA operations dashboard for **Jira Server/Data Center + Xray Raven 1.0**, existing **Pytest/Playwright** automation, and FLBv3 Windows PowerShell runs.

> **Development / validation status:** Implemented features are not yet verified end-to-end against the company Jira or a Windows VM. The public Vercel site is a **synthetic-data demo**, not a live Jira connection or remote test runner. Do not expose the local backend to the LAN or internet: it has no user authentication.

## Features currently in the repository

| Area | Implementation | Important limitation |
| --- | --- | --- |
| Repository discovery | Register trusted local folders; collect Pytest node IDs; map NJM issue keys | Does not edit automation source |
| Jira / Xray | Read-only Test Plan snapshot, execution membership, TC details, Test Run details and statuses | Requires a reachable Jira Server/DC and PAT |
| Jira connection settings | Enter a masked PAT, save in backend process memory, test connection, clear runtime PAT | Loopback-only; PAT is lost on restart |
| Suites and sequential runs | Save suites and launch opt-in local sequential runs | Requires local runner enablement; persistence of execution-scoped Test Run IDs remains incomplete |
| FLBv3 PowerShell runner | Start selected waves or retry an existing run; stop the managed process | Windows-only, opt-in, process-local lock; actual script compatibility not yet verified |
| Run monitoring and results | JSONL monitoring, JUnit reconciliation, retry history and failure reason | JUnit verdict ordering uses file modification times and is provisional |
| Failure review | Locally record reason, classification, defect reference and reviewer | Human decision; no Jira writes |
| Manual spec check | Mark NOT_VERIFIED / VERIFIED / NEEDS_UPDATE **only for a FAILED TC whose failure reason remains unclear** | QA checks spec manually; server verifies FAILED JUnit status, not whether the reason is truly unclear |
| Evidence cross-check | Read-only bundle of Jira TC, optional Xray Test Run ID and local JUnit evidence | Specification source is not connected |

No automatic Confluence/spec verification is planned for the current workflow. No Jira updates, defect creation or Xray status publication are implemented.

## Quick start: Windows VM

**Prerequisites:** Git, Python 3, Node.js/npm, PowerShell, access to the private Jira network (for Jira features), and a separately cloned trusted FLBv3 automation repository (for FLBv3 features).

Clone the Hub:

```powershell
git clone https://github.com/barotri-ton/QA-Automation-Hub.git
cd QA-Automation-Hub
```

Terminal 1 — backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:QA_HUB_ALLOW_LOCAL_PATHS = "true"
$env:QA_HUB_ENABLE_FLBV3_RUNNER = "true"
$env:QA_HUB_ENABLE_RUNNER = "true"

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend (from repository root):

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL shown by Vite (typically `http://127.0.0.1:5173`). Backend API documentation: `http://127.0.0.1:8000/docs`.

### Configure Jira PAT in the UI

1. In the **local Windows application**, find **Settings · Jira Connection**.
2. Enter the Jira Base URL (the local UI defaults to `http://10.170.180.181:8080`) and paste your Jira **Personal Access Token** into the masked field.
3. Click **Save PAT locally**, then **Test connection**.
4. A successful test uses Jira's read-only `/rest/api/2/myself` endpoint. You can then import Test Plans in Xray Review.
5. Use **Clear runtime PAT** to discard the UI-entered credential. Restarting the backend also clears it.

**Credential handling:** The UI-entered PAT is sent to the loopback backend and retained **only in backend process memory**; the backend never returns the token. It is **not** saved to SQLite, localStorage, the repository, or Vercel. The configuration endpoint rejects non-loopback clients and untrusted browser origins. Do not use it through a public reverse proxy. If a durable configuration is required, set `QA_HUB_JIRA_BASE_URL` and `QA_HUB_JIRA_PAT` as backend environment variables from your secure local store; runtime UI settings take precedence until cleared.

Do **not** paste a real PAT into the public demo at https://qa-automation-hub-demo.vercel.app — its Settings page is a disabled mockup.

### Register and investigate FLBv3 runs

Register the **local folder path** to your existing `flb-automation` clone (not its GitHub URL). The Hub expects `scripts/flbv3/run_flbv3.ps1` and `run_flbv3_retry.ps1` for execution, and `results/runs/<run_id>/flbv3-run.json` for existing run discovery.

In **FLBv3 Results**, select a repository and run, inspect the FAILED/BROKEN/SKIPPED reasons, and open a TC review. The **Compare Jira + JUnit** action accepts an optional execution-scoped Xray Test Run ID. The backend reads Jira and runner evidence without changing Jira.

**Manual spec verification is exceptional, not a routine step:**

1. Investigate the runner evidence and failure reason first.
2. Only when the TC is **FAILED** and its cause is still unclear, check **Failure reason remains unclear after runner investigation**.
3. QA manually checks the specification outside the Hub, then records `NOT_VERIFIED`, `VERIFIED`, or `NEEDS_UPDATE` with reviewer and optional note.
4. A spec marker does **not** automatically imply Product Bug, Obsolete TC or Passed. For PASSED, BROKEN and SKIPPED tests, spec verification is not applicable.

## Public demo

[Open QA Automation Hub demo](https://qa-automation-hub-demo.vercel.app)

The demo uses synthetic NJM test cases and executions, a sample review workflow, local browser-only notes and export. It **cannot** reach the internal Jira, access your Windows VM or execute automation. Its PAT field is intentionally disabled.

## Development checks

```powershell
# From backend/ with venv activated
python -m pytest -q

# From frontend/
npm run build
```

These checks are recommended after cloning; they are **not** evidence that the real Windows/Jira integration has passed. Real E2E validation is intentionally deferred to the user's Windows VM.

## Security and operating boundaries

- Run the backend on `127.0.0.1` with **one worker**. It has no login/authentication or machine-wide runner lock.
- Never commit PATs, automation credentials, company automation source, internal reports or real evidence to Git.
- Runner operations can have side effects. Review wave selection, preflight, cleanup, retry and gated operations before starting; use an authorized lab.
- No automatic Jira writes. Existing automation source must not be created, edited or deleted by the Hub.
- JUnit file modification time is not an authoritative retry sequence. Cross-check final status against Allure/runner evidence.
- Some integration and local-only features require validation on the actual Windows environment before production use.

## Documentation

- [Windows VM smoke-test guide](LOCAL_WINDOWS_TEST.md)
- [Local development](docs/LOCAL_DEVELOPMENT.md)
- [Project handoff status](HANDOFF_STATUS.md)

## Roadmap

1. Validate Windows runner compatibility, Jira PAT connection and existing run inventory on the user's VM.
2. Strengthen evidence links, retry reconciliation and failure classification reasons.
3. Improve run history, diagnostics and dashboard usability.
4. Add safe persistence and migration strategy for local metadata; retain human review and read-only Jira boundaries.
