# Xray Preview API — development contract

The current endpoints operate on **client-supplied sample/snapshot data**.
They do not connect to Jira, persist a suite, start a runner, or sync results.

## Review a Test Plan

`POST /api/xray/preview/review`

Example body:

```json
{
  "jira_key": "NJM-1000",
  "executions": [
    {
      "jira_key": "NJM-1100",
      "summary": "Smoke",
      "cases": [
        {"jira_key": "NJM-101", "summary": "Login"},
        {"jira_key": "NJM-102", "summary": "Backup"}
      ]
    },
    {
      "jira_key": "NJM-1200",
      "summary": "Regression",
      "cases": [
        {"jira_key": "NJM-101", "summary": "Login again"}
      ]
    }
  ],
  "mappings": {
    "NJM-101": "test_login.py::test_login"
  }
}
```

## Build a sequential suite preview

`POST /api/xray/preview/suite`

Use the same body and add:

```json
{
  "selected": {
    "NJM-1100": ["NJM-101", "NJM-102"],
    "NJM-1200": ["NJM-101"]
  }
}
```

The response includes `mode: SEQUENTIAL`, `preview_only: true`,
execution-group summaries, case-instance status, and missing-automation totals.

## Important distinctions

- `NJM-101` in two executions creates two distinct suite instances.
- Missing automation is not counted as FAIL or SKIP.
- No execution or Xray write-back occurs from these endpoints.
- A production Jira adapter must validate Test Plan membership, pagination,
  project permissions, and Xray Data Center version-specific endpoints.
- This local development API is unauthenticated and must remain loopback-only.
