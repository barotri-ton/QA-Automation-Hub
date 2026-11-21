import {useState} from "react";
type Repo={id:number;name:string};
type Result={run_id:string;counts:Record<string,number>;cases:{key:string;test:string;status:string;reason:string;duration:string|null;report:string}[];attempts:number;reports_scanned:number};
export default function Flbv3Results({repositories}:{repositories:Repo[]}){
 const [repo,setRepo]=useState("");const [run,setRun]=useState("");const [data,setData]=useState<Result|null>(null);const [error,setError]=useState("");const [busy,setBusy]=useState(false);const [filter,setFilter]=useState("ALL");
 const [selected,setSelected]=useState<string|null>(null);const [details,setDetails]=useState<unknown>(null);
 async function load(){setBusy(true);setError("");try{const response=await fetch(`/api/flbv3/repositories/${repo}/runs/${encodeURIComponent(run)}/results`);const json=await response.json();if(!response.ok)throw new Error(json.detail||"Cannot read reports");setData(json);}catch(e){setError(String(e));}finally{setBusy(false);}}
 async function jira(key:string){setSelected(key);setDetails(null);try{const r=await fetch(`/api/jira/tests/${key}`);const d=await r.json();if(!r.ok)throw new Error(d.detail);setDetails(d);}catch(e){setDetails({error:String(e)});}}
 const shown=data?.cases.filter(c=>filter==="ALL"||c.status===filter)??[];
 return <section className="panel"><h2>FLBv3 Results · Failure Investigation</h2><p className="hint">Read-only JUnit analysis. Classifying product bug vs obsolete TC requires manual review against Jira and specifications; no automated conclusion or Jira update.</p>
 <div className="xray-actions"><select value={repo} onChange={e=>setRepo(e.target.value)}><option value="">Select repository</option>{repositories.map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select><input placeholder="Run folder" value={run} onChange={e=>setRun(e.target.value)}/><button disabled={!repo||!run||busy} onClick={()=>void load()}>Analyze results</button></div>
 {error&&<p role="alert">{error}</p>}
 {data&&<><p>JUnit reports: {data.reports_scanned} · Test attempts: {data.attempts}</p><div className="xray-actions">{["ALL","PASSED","FAILED","BROKEN","SKIPPED"].map(k=><button key={k} onClick={()=>setFilter(k)}>{k} {k==="ALL"?data.cases.length:data.counts[k]}</button>)}</div>
 <table><thead><tr><th>Test Case</th><th>Status</th><th>Reason / Evidence</th><th>Jira</th></tr></thead><tbody>{shown.map(c=><tr key={c.key}><td>{c.key}</td><td>{c.status}</td><td><strong>{c.reason||"No failure message"}</strong><small>{c.report}</small></td><td><button onClick={()=>void jira(c.key)}>Review Jira</button></td></tr>)}</tbody></table>
 {selected&&<details open><summary>Jira details · {selected}</summary><pre style={{whiteSpace:"pre-wrap",overflowWrap:"anywhere",maxHeight:420,overflow:"auto"}}>{details?JSON.stringify(details,null,2):"Loading..."}</pre></details>}</>}
 </section>;
}
