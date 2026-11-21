import {useEffect, useState} from "react";

type CaseRow = {key:string;status:string;attempts:number};
type Monitor = {run_id:string;state:string;planned:number;cases:CaseRow[];active_workers:{key:string;pid:number|null}[];event_count:number;note:string};
type Repo = {id:number;name:string};

export default function Flbv3Monitor({repositories}:{repositories:Repo[]}) {
  const [repositoryId,setRepositoryId] = useState("");
  const [runId,setRunId] = useState("");
  const [data,setData] = useState<Monitor|null>(null);
  const [error,setError] = useState("");
  useEffect(()=>{
    if (!repositoryId || !runId || !/^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}$/.test(runId)) return;
    let stopped=false;
    async function refresh(){
      try {
        const response=await fetch(`/api/flbv3/repositories/${repositoryId}/runs/${encodeURIComponent(runId)}/monitor`);
        if(!response.ok) throw new Error(`Monitor HTTP ${response.status}`);
        const next:Monitor=await response.json();
        if(!stopped){setData(next);setError("");}
      } catch(e){if(!stopped){setError(String(e));setData(null);}}
    }
    void refresh();
    const timer=setInterval(()=>void refresh(),2000);
    return ()=>{stopped=true;clearInterval(timer);};
  },[repositoryId,runId]);
  return <section className="panel">
    <h2>FLBv2v3 · Live Wave Monitor (read-only)</h2>
    <p>Choose a registered local automation repository and an existing results/runs folder. No scripts are launched or modified.</p>
    <label>Repository <select value={repositoryId} onChange={e=>setRepositoryId(e.target.value)}>
      <option value="">Select repository</option>
      {repositories.map(repo=><option key={repo.id} value={repo.id}>{repo.name}</option>)}
    </select></label>
    <label>Run folder name <input value={runId} onChange={e=>setRunId(e.target.value)} placeholder="20261121-120000-000"/></label>
    {error&&<p role="alert">{error}</p>}
    {data&&<div aria-live="polite">
      <p><strong>{data.state}</strong> · {data.planned} planned · {data.active_workers.length} active workers · {data.event_count} events</p>
      <p>{data.note}</p>
      <table><thead><tr><th>TC</th><th>Event status</th><th>File attempts</th></tr></thead><tbody>
        {data.cases.map(c=><tr key={c.key}><td>{c.key}</td><td>{c.status}</td><td>{c.attempts}</td></tr>)}
      </tbody></table>
    </div>}
  </section>;
}
