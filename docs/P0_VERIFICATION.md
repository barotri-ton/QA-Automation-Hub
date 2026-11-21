# P0 verification

Run backend tests with `PYTHONPATH=backend pytest -q backend/tests` from the repository root, and run `npm install && npm run build` inside `frontend`.

Pytest collection imports test modules and runs plugin hooks. Scan only trusted projects. Do not expose the unauthenticated development API outside loopback. Never commit internal scripts, Jira tokens or environment credentials.

Current gaps: per-project interpreter selection, async scan job tracking, verified CI, Jira PAT vault and Xray API adapter.
