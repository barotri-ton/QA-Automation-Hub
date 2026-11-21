# QA Automation Hub

Local-first automation test management dashboard for Pytest and Playwright, integrated with Jira Xray Server/Data Center.

## Goals

- Register and discover existing local automation projects without editing their source code.
- Read pytest markers containing Jira issue keys such as `NJM-1234`.
- Import Jira Xray Test Plans and Test Executions via Jira Personal Access Token (PAT).
- Map Jira Test Cases to collected pytest node IDs and identify missing automation per Test Plan.
- Build editable test selections and run them using a local runner.
- Monitor execution status, logs, screenshots, videos, traces, and results.
- Review results before any write-back to Xray.

## Proposed stack

- Frontend: React, TypeScript, Vite
- Backend: Python, FastAPI
- Metadata: SQLite / SQLAlchemy
- Execution: isolated Pytest subprocess with Playwright support
- Live monitoring: WebSocket

## Product rules

1. The dashboard is **read-only with respect to automation test script source code**. Scripts are authored and maintained separately.
2. Never commit Jira PATs, internal URLs, test data, or company source code.
3. A missing automation mapping is **MISSING**, not FAIL or SKIPPED.
4. Never sync execution results to Jira Xray without an explicit review and confirmation.
5. Preserve run manifests and execution history independently of later repository changes.

## Planned phases

- **P0:** Project foundation, repository registration, pytest discovery, marker mapping.
- **P1:** Jira PAT connection, Xray import, coverage tracking, missing automation backlog, suite builder.
- **P2:** Local runner, preflight checks, live monitoring, evidence collection.
- **P3:** Failure triage, reports, flaky analysis, reviewed Xray sync.
- **P4:** Remote runners, scheduling, advanced analytics.

> Status: project initialization. Features described above are planned, not implemented.
