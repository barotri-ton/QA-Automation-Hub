# P0 Foundation — Acceptance Criteria

## Functional

- [ ] Backend health endpoint responds at /api/health
- [ ] Local repository registration is disabled unless explicitly enabled
- [ ] Register a trusted local Pytest project
- [ ] Collect Pytest node IDs without executing test bodies
- [ ] Map marker arguments containing NJM-1234
- [ ] Show unmapped items and ambiguous mappings separately
- [ ] Preserve records for test items missing from later scans
- [ ] Frontend builds and displays registered repositories

## Security and boundaries

- [ ] Test script source code remains unchanged after scanning (ignore Pytest-generated caches)
- [ ] No company test scripts or credentials committed to this repository
- [ ] Local API is bound to loopback only; no public exposure
- [ ] Jira PAT storage and authentication are **out of scope for P0**

## Known limitations

- The scanner runs in the backend Python interpreter, not yet a per-project venv.
- Pytest collection executes imports and plugin hooks; scan only trusted projects.
- No job queue, run cancellation, API authentication, or Xray sync yet.
- No automated test run is claimed successful until CI completes.
