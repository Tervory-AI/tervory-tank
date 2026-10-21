"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { readBaselineSettings, saveBaseline } from "./savings-founder-actions";
type Settings = { tasks: {task_type:string; standard:string|null; top:string|null; override_model:string|null; choices:string[];quality_compared:boolean}[]; changes:{id:string;task_type:string;old_model:string|null;new_model:string|null;by_user:string;created_at:string;rows_updated:number;status:string;error?:string|null}[] };
export function BaselineControls({initial}:{initial:Settings}) {
  const [data,setData]=useState(initial),[busy,setBusy]=useState(false),[error,setError]=useState(false);
  const router=useRouter();
  useEffect(()=>{
    if(!data.changes.some(c=>c.status==='pending'||c.status==='running'))return;
    const timer=setInterval(async()=>{try{const next:Settings=await readBaselineSettings();setData(next);if(!next.changes.some(c=>c.status==='pending'||c.status==='running'))router.refresh();}catch{setError(true);}},5000);
    return()=>clearInterval(timer);
  },[data.changes,router]);
  async function submit(form:FormData){setBusy(true);setError(false);try{await saveBaseline(String(form.get('task')),String(form.get('model')||'')||null);setData(await readBaselineSettings());router.refresh();}catch{setError(true);}finally{setBusy(false);}}
  return <details className="savings-costs"><summary>Baseline settings · founder only</summary><p>The provider’s standard model always leads the headline. A task override adds a named comparison; it cannot replace the standard headline. Changes re-price past rows in batches and keep earlier report cutoffs available.</p>
    {error&&<p role="alert">Baseline settings could not be updated. Refresh to check the saved state.</p>}
    {data.tasks.map(t=><section key={t.task_type}><h3>{t.task_type}</h3><form action={submit}><input type="hidden" name="task" value={t.task_type}/><label>Baseline<select aria-label={`Baseline for ${t.task_type}`} name="model" key={t.override_model??'default'} defaultValue={t.override_model??''}><option value="">Provider standard: {t.standard??'not priced'}</option>{t.choices.map(name=><option key={name} value={name}>{name}</option>)}</select></label><button disabled={busy}>Save baseline and re-price</button></form><p>Headline: standard {t.standard??'not priced'} · Second line: vs the top model ({t.top??'not priced'})</p>{!t.quality_compared&&<p>same work assumed; quality comparison pending</p>}</section>)}
    <h3>Baseline change history</h3>{!data.changes.length&&<p>No changes yet.</p>}{data.changes.map(c=><p key={c.id}>{c.task_type}: {c.old_model??'previous comparison'} → {c.new_model??'provider standard'} · {c.by_user} · {c.created_at} · {c.status} · {c.rows_updated} rows re-priced {c.error??""}</p>)}
  </details>;
}
