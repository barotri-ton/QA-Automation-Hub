# QA Automation Hub

Local-first QA automation dashboard for Jira Xray Server/Data Center, Pytest and Playwright.

## Current implementation (P0 scaffold)

- React + TypeScript + Vite repository manager UI
- FastAPI + SQLite local metadata backend
- Register trusted local automation directories (opt-in)
- Collect Pytest node IDs and detect NJM Jira markers
- Track unmapped, ambiguous and disappeared test items
- Basic backend tests and GitHub Actions CI

## Run locally

See [Local Development](docs/LOCAL_DEVELOPMENT.md).

## Roadmap

- P1: Jira PAT, Xray import, Test Plan coverage and missing automation backlog
- P2: runner, execution preflight, live monitoring, evidence
- P3: analytics, failure triage, reviewed Xray sync
- P4: multi-runner and advanced features

## Boundaries

Test script source code is maintained separately in your IDE. This dashboard only indexes, maps and (in a later phase) runs existing scripts; it must not create, edit or delete test scripts. Never commit company automation source, internal URLs or Jira PATs.

> Status: early P0 scaffold. No Jira connection or execution runner yet. Do not expose this unauthenticated local development service to a network.
