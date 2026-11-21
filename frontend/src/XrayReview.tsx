import { useState } from "react";

type Case = { jira_key: string; summary?: string };
type Execution = { jira_key: string; summary?: string; cases: Case[] };
type Plan = { jira_key: string; executions: Execution[]; mappings: Record<string, string> };
type Group = { execution_key: string; case_instances: { jira_key: string; nodeid: string | null; status: string }[] };
type Preview = { mode: string; preview_only: boolean; run: { total: number; missing_automation: number; groups: { execution_key: string; status: string; total: number; missing_automation: number }[] }; cases: Group[] };

const EXAMPLE: Plan = {
  jira_key: "NJM-1000",
  executions: [
    { jira_key: "NJM-1100", summary: "Smoke", cases: [
      { jira_key: "NJM-101", summary: "Login" },
      { jira_key: "NJM-102", summary: "Backup" },
    ] },
    { jira_key: "NJM-1200", summary: "Regression", cases: [
      { jira_key: "NJM-101", summary: "Login again" },
      { jira_key: "NJM-201", summary: "Restore" },
    ] },
  ],
  mappings: { "NJM-101": "test_login.py::test_login" },
};

const idFor = (execution: string, test: string) => JSON.stringify([execution, test]);

export default function XrayReview() {
  const [source, setSource] = useState(JSON.stringify(EXAMPLE, null, 2));
  const [plan, setPlan] = useState<Plan | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<Preview | null>(null);
  const [savedSuiteId, setSavedSuiteId] = useState<string | null>(null);
  const [createdRunId, setCreatedRunId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function post(endpoint: string, payload: unknown) {
    const response = await fetch(`/api/xray/preview/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(
      typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)
    );
    return data;
  }

  async function load() {
    setLoading(true);
    setError("");
    setPreview(null);
    setSavedSuiteId(null);
    setCreatedRunId(null);
    try {
      const parsed: Plan = JSON.parse(source);
      const result = await post("review", parsed);
      const next = new Set<string>();
      for (const execution of result.executions as Execution[]) {
        for (const test of execution.cases) next.add(idFor(execution.jira_key, test.jira_key));
      }
      setPlan(parsed);
      setSelected(next);
      setExpanded(new Set(parsed.executions.map(execution => execution.jira_key)));
    } catch (e) {
      setPlan(null);
      setError(e instanceof Error ? e.message : "Could not load snapshot");
    } finally {
      setLoading(false);
    }
  }

  function toggleCase(key: string) {
    setPreview(null);
    setSavedSuiteId(null);
    setCreatedRunId(null);
    setSelected(current => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleGroup(execution: Execution, checked: boolean) {
    setPreview(null);
    setSavedSuiteId(null);
    setCreatedRunId(null);
    setSelected(current => {
      const next = new Set(current);
      for (const test of execution.cases) {
        const key = idFor(execution.jira_key, test.jira_key);
        if (checked) next.add(key); else next.delete(key);
      }
      return next;
    });
  }

  async function createPreview() {
    if (!plan) return;
    setLoading(true);
    setError("");
    try {
      const groups: Record<string, string[]> = {};
      for (const execution of plan.executions) {
        const cases = execution.cases.filter(test =>
          selected.has(idFor(execution.jira_key, test.jira_key))
        ).map(test => test.jira_key);
        if (cases.length) groups[execution.jira_key] = cases;
      }
      const result = await post("suite", { ...plan, selected: groups });
      setSavedSuiteId(null);
      setCreatedRunId(null);
      setPreview(result as Preview);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Suite preview failed");
    } finally {
      setLoading(false);
    }
  }

  async function saveSuite() {
    if (!plan || !preview) return;
    setLoading(true);
    setError("");
    try {
      const groups: Record<string, string[]> = {};
      for (const execution of plan.executions) {
        const cases = execution.cases.filter(test =>
          selected.has(idFor(execution.jira_key, test.jira_key))
        ).map(test => test.jira_key);
        if (cases.length) groups[execution.jira_key] = cases;
      }
      const response = await fetch("/api/suites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...plan, selected: groups }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(data.detail));
      setSavedSuiteId(data.suite_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  async function createRunRecord() {
    if (!savedSuiteId) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/suites/${savedSuiteId}/runs`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(JSON.stringify(data.detail));
      setCreatedRunId(data.run_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run record creation failed");
    } finally {
      setLoading(false);
    }
  }

  const selectedCount = selected.size;
  const missingCount = plan?.executions.reduce((count, execution) =>
    count + execution.cases.filter(test =>
      selected.has(idFor(execution.jira_key, test.jira_key)) &&
      !plan.mappings[test.jira_key]
    ).length, 0) ?? 0;

  return <section className="panel xray-review">
    <h2>Xray Test Plan Review · Sequential Suite Builder</h2>
    <p className="hint"><strong>Preview mode:</strong> Paste a Test Plan snapshot as JSON. The example is synthetic; Jira import, persistence and execution are not connected yet.</p>
    <label htmlFor="xray-json">Test Plan snapshot JSON</label>
    <textarea id="xray-json" rows={8} value={source} onChange={event => setSource(event.target.value)} spellCheck={false} />
    <div className="xray-actions">
      <button disabled={loading} onClick={() => void load()}>Review snapshot</button>
      {plan && <button disabled={loading || selectedCount === 0} onClick={() => void createPreview()}>Build sequential suite preview</button>}
    </div>
    {error && <p role="alert" className="xray-error">{error}</p>}
    {plan && <>
      <h3>{plan.jira_key} · {plan.executions.length} Test Executions</h3>
      <p className="hint">Selected: {selectedCount} case instances · Missing automation: {missingCount} · Execution order follows the plan snapshot.</p>
      {plan.executions.map(execution => {
        const checked = execution.cases.filter(test => selected.has(idFor(execution.jira_key, test.jira_key))).length;
        return <div className="xray-group" key={execution.jira_key}>
          <div className="xray-group-header">
            <input type="checkbox" aria-label={`Select all ${execution.jira_key}`} checked={checked === execution.cases.length && checked > 0} onChange={event => toggleGroup(execution, event.target.checked)} />
            <button className="xray-expand" aria-expanded={expanded.has(execution.jira_key)} onClick={() => setExpanded(current => {
              const next = new Set(current);
              if (next.has(execution.jira_key)) next.delete(execution.jira_key); else next.add(execution.jira_key);
              return next;
            })}>{expanded.has(execution.jira_key) ? "▾" : "▸"} {execution.jira_key} · {execution.summary || "Test Execution"}</button>
            <span>{checked}/{execution.cases.length} selected</span>
          </div>
          {expanded.has(execution.jira_key) && <div className="xray-cases">{execution.cases.map(test =>
            <label key={test.jira_key} className="xray-case">
              <input type="checkbox" checked={selected.has(idFor(execution.jira_key, test.jira_key))} onChange={() => toggleCase(idFor(execution.jira_key, test.jira_key))} />
              <span>{test.jira_key} · {test.summary || "Test Case"}</span>
              <small className={plan.mappings[test.jira_key] ? "xray-mapped" : "xray-missing"}>{plan.mappings[test.jira_key] ? "Mapped" : "Missing automation"}</small>
            </label>
          )}</div>}
        </div>;
      })}
    </>}
    {preview && <div className="xray-preview" aria-live="polite">
      <h3>Suite preview · {preview.mode}</h3>
      <p className="hint">{preview.run.total} runnable instances · {preview.run.missing_automation} missing automation · No tests started</p>
      <div className="xray-actions">
        <button disabled={loading || !!savedSuiteId} onClick={() => void saveSuite()}>Save suite snapshot</button>
        {savedSuiteId && <button disabled={loading || !!createdRunId} onClick={() => void createRunRecord()}>Create run record (no execution)</button>}
      </div>
      {savedSuiteId && <p className="hint">Saved suite: <code>{savedSuiteId}</code></p>}
      {createdRunId && <p className="hint">Run record: <code>{createdRunId}</code> · No runner started</p>}
      {preview.run.groups.map((group, index) => <div key={group.execution_key} className="xray-preview-row">
        <strong>{index + 1}. {group.execution_key}</strong>
        <span>{group.status} · {group.total} runnable · {group.missing_automation} missing</span>
      </div>)}
    </div>}
  </section>;
}
