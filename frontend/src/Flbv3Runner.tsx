import {useEffect,useState} from "react";
type Repo={id:number;name:string};
type State={active:boolean;pid:number|null;run:{repository_id:number;run_id:string|null;retry:boolean}|null};
export default function Flbv3Runner({repositories}:{repositories:Repo[]}) {
 const [repositoryId,setRepositoryId]=useState("");
 const [waves,setWaves]=useState("1,2,3,5,6,7,8");
 const [parallel,setParallel]=useState(5);
 const [allow,setAllow]=useState<string[]>([]);
 const [confirm,setConfirm]=useState(false);
 const [retry,setRetry]=useState(false);
 const [runId,setRunId]=useState("");
 const [only,setOnly]=useState("");
 const [exclude,setExclude]=useState("");
 const [state,setState]=useState<State|null>(null);
 const [message,setMessage]=useState("");
 const [busy,setBusy]=useState(false);
 async function refresh(){
  try{const r=await fetch("/api/flbv3/runner/status");if(r.ok)setState(await r.json());}catch{/* backend offline */}
 }
 useEffect(()=>{void refresh();const timer=setInterval(()=>void refresh(),2000);return()=>clearInterval(timer);},[]);
 async function action(path:string,body?:object){
  setBusy(true);setMessage("");
  try{const r=await fetch(`/api/flbv3/runner/${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body??{})});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==="string"?d.detail:JSON.stringify(d.detail));setMessage(JSON.stringify(d));await refresh();}
  catch(e){setMessage(e instanceof Error?e.message:String(e));}finally{setBusy(false);}
 }
 const gates=["repo-maintenance","tape","flr-to-source","destructive","license"];
 return <section className="panel">
 <h2>FLBv3 PowerShell Runner · Windows only</h2>
 <p className="hint">Runs scripts in the registered local repository. Gated actions can alter the lab. Enable only on a trusted loopback backend.</p>
 <label>Repository <select value={repositoryId} onChange={e=>setRepositoryId(e.target.value)}><option value="">Select</option>{repositories.map(r=><option value={r.id} key={r.id}>{r.name}</option>)}</select></label>
 <label><input type="checkbox" checked={retry} onChange={e=>setRetry(e.target.checked)}/> Retry failed/broken in existing run</label>
 <label>Run folder {retry?"(required)":"(created automatically for full run)"}<input disabled={!retry} value={runId} onChange={e=>setRunId(e.target.value)} placeholder="20261121-120000-000"/></label>
 {retry?<><label>Only TC keys (optional)<input value={only} onChange={e=>setOnly(e.target.value)} placeholder="NJM-101,NJM-102"/></label><label>Exclude TC keys<input value={exclude} onChange={e=>setExclude(e.target.value)}/></label></>:
 <label>Waves (1–9)<input value={waves} onChange={e=>setWaves(e.target.value)}/></label>}
 <label>Parallel workers <input type="number" min={1} max={6} value={parallel} onChange={e=>setParallel(Number(e.target.value))}/></label>
 <p>Explicitly allowed gates:</p>
 {gates.map(g=><label key={g}><input type="checkbox" checked={allow.includes(g)} onChange={e=>setAllow(old=>e.target.checked?[...old,g]:old.filter(x=>x!==g))}/>{g}</label>)}
 <label><input type="checkbox" checked={confirm} onChange={e=>setConfirm(e.target.checked)}/> I understand gated tests may modify or delete lab resources</label>
 <p>Process: {state?.active?`RUNNING (PID ${state.pid})`:"Idle / not managed by this backend"}</p>
 <div className="xray-actions">
 <button disabled={busy||!!state?.active||!repositoryId||retry&&!runId} onClick={()=>void action("start",{
 repository_id:Number(repositoryId),retry,run_id:runId||null,
 waves:waves.split(",").map(x=>Number(x.trim())),parallel,allow,confirm_gated:confirm,
 only:only.split(",").map(x=>x.trim()).filter(Boolean),exclude:exclude.split(",").map(x=>x.trim()).filter(Boolean)
 })}>Start {retry?"retry":"wave run"}</button>
 <button disabled={busy||!state?.active} onClick={()=>{if(window.confirm("Force stop runner and child processes?"))void action("stop");}}>Force stop process tree</button>
 </div>
 {message&&<p role="status">{message}</p>}
 </section>;
}
