# Xray Test Plan → Test Execution → Test Case workflow

## Import and review

1. User enters an Xray Test Plan issue key (for example NJM-1000).
2. Server-side Jira/Xray adapter loads the Test Plan, its associated Test Executions, and the Test Cases assigned to each execution. Actual Xray Server/Data Center endpoints and pagination must be verified against the company's installed Xray version.
3. Dashboard presents an expandable tree: Plan → Execution → Test Case. Show issue key, summary, Jira status, last execution status when available, automation mapping, and missing-automation flags.
4. User reviews, selects, and optionally excludes execution groups or individual cases before saving the suite.
5. Preserve a versioned import snapshot (source issue keys, fetched-at timestamp, membership, and mapping); Jira can change after import.

## Suite semantics

- The suite is a **snapshot** of a selected Test Plan and selected Test Executions.
- The grouping key is the original Xray Test Execution issue key, not merely a test label.
- Each selected Test Case is a distinct **suite execution instance** scoped to its parent Test Execution.
- If the same Jira Test Case belongs to two Test Executions, retain two instances and independently track their progress, attempts, and results.
- Unmapped Test Cases are marked MISSING_AUTOMATION and must not be treated as failed or skipped pytest tests.
- Preserve explicit exclusion reasons; show selected/automated/missing/excluded totals.
- A Test Execution with no runnable mapped tests is BLOCKED or NOT_RUN, not COMPLETED.

## Runner and live monitoring

- At run start, freeze a run manifest: plan key, suite revision, execution group IDs/keys, selected test case instances, pytest node IDs, environment, and mapping version.
- Initially process groups sequentially, but design event identifiers for future parallel execution.
- Emit events keyed by `run_id`, `group_id`, and `case_instance_id`; events include attempt number and monotonic sequence number to avoid double-counting reconnect/retry updates.
- Group lifecycle: QUEUED → RUNNING → COMPLETED / COMPLETED_WITH_FAILURES / BLOCKED / CANCELLED.
- Case lifecycle: QUEUED → RUNNING → PASSED / FAILED / SKIPPED / ERROR / CANCELLED; MISSING_AUTOMATION is a separate mapping state.
- Progress is computed from **selected case instances**, not unique Jira issue keys. A retry updates its original instance; it does not inflate completion count.
- Group completion requires every selected runnable instance to reach a terminal state. Failure counts affect group outcome, not completion eligibility.
- UI shows per-group counts (total, completed, passed, failed, skipped, error, missing, running, queued), elapsed time, and expandable test/evidence details.
- Persist progress and event history to allow page refresh and reconnect without losing group state.

## Jira safety

- Read-only import first. Xray write-back is not part of initial import or runner.
- Never automatically create/modify Xray Test Executions or overwrite manual results.
- Later write-back requires review and explicit confirmation, preserving original Test Execution association.
- PAT remains on the backend, never in browser storage or logs.

## Acceptance scenarios

1. Plan with two executions: first completed, second running — dashboard reflects both independently.
2. One TC appears in two executions — two instances are shown and counted.
3. One execution has 3 PASS and 1 FAIL — status COMPLETED_WITH_FAILURES, not RUNNING.
4. One execution has only unmapped TCs — status BLOCKED; missing does not count as FAIL.
5. Retry a failed case — completed/total does not increase twice.
6. Browser reload — group statuses restore from persisted run state.
7. Exclude one TC from suite — it remains visible in review, but not run denominator.
8. Cancellation — active and queued groups have accurate terminal/remaining states.
