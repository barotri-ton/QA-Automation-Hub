# Local sequential Pytest runner — implementation status

`backend/app/local_runner.py` now provides a synchronous Python execution
function, `run_sequential`, for trusted local Pytest projects.

## Guarantees

- One selected Pytest node ID at a time.
- Test Execution group A completes before group B begins.
- A TC appearing in two groups is executed once per selected instance.
- JUnit XML determines PASS / FAIL / SKIP / ERROR.
- Missing automation is not run and is not counted as a Pytest failure.
- A callback fires at case start and completion so a future job manager can
  persist progress after each transition.

## Limitations and security

- **Not yet wired to the HTTP API or the dashboard Start Runner button.**
- The current API creates a run record but does not start a subprocess.
- No subprocess cancellation, restart recovery, WebSocket stream, or evidence
  attachment is implemented.
- Only trusted test repositories may be executed: collection and execution
  import user test code, fixtures and plugins.
- The runner sets PYTHONDONTWRITEBYTECODE and disables pytest cacheprovider,
  but cannot guarantee source-tree immutability because test code and plugins
  can create or modify files.
- stdout/stderr are captured in memory and not returned to clients or stored.
  Detailed failure evidence and log redaction are pending.
- The interpreter can be provided to the Python function, but per-repository
  environment configuration is not yet exposed in the UI.
- Never expose the unauthenticated development server outside loopback.

## Next integration tasks

1. Validate all CI tests and frontend build.
2. Add trusted repository binding and preflight to run manifests.
3. Implement a persistent background worker with one active local run,
   crash recovery and cancellation.
4. Add run events and polling or WebSocket progress by execution group.
5. Build version-verified Jira/Xray Server/Data Center importer, without
   sending a PAT to the frontend or committing it to Git.
