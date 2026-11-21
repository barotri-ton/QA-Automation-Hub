# Local Windows VM smoke test — QA Automation Hub

The FLBv3 integration is **opt-in** and must run only on a trusted Windows VM with the backend bound to 127.0.0.1. Do not expose these endpoints to a LAN or internet; no authentication is implemented.

## Setup

```powershell
git clone https://github.com/barotri-ton/QA-Automation-Hub.git
cd QA-Automation-Hub
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:QA_HUB_ALLOW_LOCAL_PATHS = "true"
$env:QA_HUB_JIRA_BASE_URL = "http://10.170.180.181:8080"
$env:QA_HUB_JIRA_PAT = "<PAT_FROM_SECURE_STORE>"
$env:QA_HUB_ENABLE_FLBV3_RUNNER = "true"
$env:QA_HUB_ENABLE_RUNNER = "true"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd QA-Automation-Hub\frontend
npm install
npm run dev
```

Register the existing trusted `flb-automation` folder in the UI (not a GitHub URL). It must already contain `scripts/flbv3/run_flbv3.ps1`, `run_flbv3_retry.ps1`, the expected virtualenv, and local test fixtures. No automation source files are modified by the Hub.

## Validation

1. Open `http://127.0.0.1:8000/docs`; confirm `/api/jira/plans/{plan_key}/snapshot` and `/api/flbv3/runner/status`.
2. In Xray Review, import `NJM-182768`. Compare all 12 executions and their Test Run IDs with Jira; validate pagination and membership.
3. Select an existing `results/runs/<run_id>` folder in Live Monitor. Confirm event updates and compare final verdicts manually against Allure/JUnit (monitor event verdicts are provisional).
4. Start a **safe, explicitly selected** wave on a disposable lab only after reviewing preflight effects. Do not enable destructive/tape/license gates unless authorized.
5. For retry, select an existing finished run and use the same run ID. Confirm attempts remain in its Allure results.

## Limitations requiring validation

- No real Jira connectivity or Windows VM execution has been tested from this development environment.
- PowerShell process lock is process-local, not a machine-wide lock. Run one backend worker only and do not run external automation concurrently.
- The runner's own preflight may perform git pull, fixture seeding and cleanup.
- Live Monitor reads JSONL events; JUnit/Allure must determine final verdicts.
- The UI does not yet publish status, defects, or evidence to Jira.
- Test Run IDs are present in live import response, but the older sequential suite persistence model does not store them.
- Never paste the Jira PAT into frontend fields or commit it to Git.
