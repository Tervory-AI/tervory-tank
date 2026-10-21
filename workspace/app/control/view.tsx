import type { DashboardRead } from "@/lib/tank";
import type { Signups } from "./sources";
import { ControlActions } from "./widgets";

export const money = (value: number | null | undefined) => value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
export function Spark({ values, green = false }: { values: number[]; green?: boolean }) {
  if (values.length < 2) return <p className="dash-note">Not enough history for a trend.</p>;
  const max = Math.max(...values), min = Math.min(...values), range = max - min || 1;
  const points = values.map((n, i) => `${i * 118 / (values.length - 1) + 1},${30 - (n - min) / range * 28}`).join(" ");
  return <svg className="dash-spark" viewBox="0 0 120 32" role="img" aria-label="Daily history"><polyline points={points} fill="none" stroke={green ? "#1e7a46" : "#001840"} strokeWidth="1.5" /></svg>;
}
export function Card({ label, value, note, values, green }: { label: string; value: string | number; note: string; values?: number[]; green?: boolean }) {
  return <section className="dash-card"><p className="dash-label">{label}</p><p className={`dash-value${green ? " dash-good" : ""}`}>{value}</p><p className="dash-note">{note}</p>{values && <Spark values={values} green={green} />}</section>;
}
const agents = ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas"];
export type FounderView = {
  data: DashboardRead | null; signups: Signups | null; paying: number | null;
  paused: boolean | null; errors: string[]; models: { task_type: string; candidate_model: string | null; n: number; agreement: number | null; min_shadow_samples?: number; eligible: boolean; prim_cost?: number | null; cand_cost?: number | null }[];
  refused: { task: string; path: string; at: string }[];
};
export function FounderDashboard({ view, squads }: { view: FounderView; squads?: import("react").ReactNode }) {
  const { data, signups, paying } = view;
  const today = new Date().toISOString().slice(0, 10);
  const daily = data?.daily ?? [];
  const day = daily.find(row => row.day === today);
  const spent = data ? daily.reduce((sum, row) => sum + Number(row.spent), 0) : null;
  const code = day && day.delivered > 0 ? `${Math.round(day.code / day.delivered * 100)}% by code` : "No completed calls today.";
  return <div className="dashboard-root dash-control">
    <header className="dash-top"><img className="dash-brand" src="/brand/tervory-logo-on-white.png" alt="Tervory" /><h1>Control panel</h1><span className="dash-health">Health unavailable · GHOST-1</span><ControlActions paused={view.paused} /></header>
    {view.errors.length > 0 && <p role="alert" className="dash-problem">{view.errors.join(" ")}</p>}
    <div className="dash-kpis">
      <Card label="Sign-ups" value={signups?.total ?? "—"} note={signups ? "From Clerk" : "Clerk unavailable"} values={signups?.days.map(day => day.value)} />
      <Card label="Paying clients" value={paying ?? "—"} note={paying == null ? "Stripe unavailable" : "Distinct customers · active paid plans"} />
      <Card label="Work done today" value={data ? day?.delivered ?? 0 : "—"} note={code} values={data?.daily.map(row => row.delivered)} />
      <Card label="Spent this month" value={money(spent)} note="Budget source not connected" values={data?.daily.map(row => Number(row.spent))} />
      <Card label="Saved this month" value={money(data?.saved_usd)} note="No recorded baseline to compare" green />
    </div>
    <div className="dash-middle">
      <section className="dash-card"><h2>Case study · AmmoSync on Base</h2><div className="dash-case-charts"><div><p className="dash-label">Verified records by state</p><div className="dash-chart-space"><p className="dash-empty">AmmoSync’s data source is not linked.</p></div></div><div><p className="dash-label">Cost per verified record</p><div className="dash-chart-space"><p className="dash-empty">No measured Apollo comparison yet.</p></div></div></div><p className="dash-empty">Headline numbers will appear when records and their costs can be attributed to this case study.</p><div className="dash-case-actions"><button className="dash-button" disabled>Run next state · AGENT-1</button><button className="dash-button" disabled>Export case study · no source</button></div></section>
      <section className="dash-card"><h2>Needs you</h2>
        <div className="dash-row"><span>{data ? `${data.skills?.length ?? 0} skills awaiting review` : "Skill reviews unavailable"}</span><button className="dash-button" disabled>Approve all ready · SKALA-2</button></div>
        {view.models.filter(row => row.candidate_model && row.eligible && row.prim_cost != null && row.cand_cost != null && row.cand_cost < row.prim_cost).map(row => <div className="dash-row" key={row.task_type}><span>{row.task_type} · {row.n} comparisons · {Math.round(Number(row.agreement) * 100)}% agreement</span><ControlActions taskType={row.task_type} /></div>)}
        <div className="dash-row"><span>Paid steps</span><span className="dash-note">No pending-action source connected</span></div>
        <div className="dash-row"><span>Daily check</span><a className="dash-button" href="/skala/gold">Open checks</a></div>
        <div className="dash-row"><span>Ghost issues unavailable</span><button className="dash-button" disabled>Look · GHOST-1</button><button className="dash-button" disabled>Let it fix · GHOST-1</button></div>
      </section>
    </div>
    <div className="dash-bottom">
      <section className="dash-card"><div className="dash-subhead"><h2>Squad</h2><span className="dash-note">This server only</span></div>{agents.map(name => {
        const key = name.toLowerCase().replaceAll(" ", "_");
        const running = data?.squad?.filter(row => row.agent === key && row.status === "running").reduce((sum,row) => sum + row.jobs, 0);
        return <div className="dash-row" key={name}><span>{name}</span><span className="dash-note">{data ? `${running ?? 0} running jobs` : "Activity unavailable"}</span><button className="dash-button" disabled>Pause / Start · AGENT-1</button></div>;
      })}<p className="dash-note">Room health and other servers are not connected.</p></section>
      <section className="dash-card"><div className="dash-subhead"><h2>Latest sign-ups</h2><a className="dash-button" href="/control/signups">All {signups?.total ?? "sign-ups"}</a></div>{signups?.recent.length ? signups.recent.map(user => <div className="dash-row" key={user.id}><span><strong>{user.name}</strong><br /><span className="dash-note">{user.company ?? "Company not provided"} · {user.country ?? "Country not provided"}</span></span><span className="dash-chip">{user.plan ?? "Plan not recorded"}</span></div>) : <p className="dash-empty">{signups ? "No sign-ups yet." : "Sign-ups could not be loaded."}</p>}</section>
      <section className="dash-card"><h2>Controls</h2><div className="dash-row"><span>Shadow checks</span><span className="dash-note">{data ? `${data.shadow_policies} policies on` : "Unavailable"} · MODELS-2</span></div><div className="dash-row"><span>Overnight batches</span><span className="dash-note">{data ? `${data.batch_policies} eligible policies` : "Unavailable"} · BATCH-1</span></div><div className="dash-row"><span>Paid tools without asking</span><span className="dash-note">No global setting · CORE-1</span></div><div className="dash-row"><span>Squad builds Tervory</span><span className="dash-note">Unavailable · AGENT-1</span></div><div className="dash-row"><span>Daily budget</span><span className="dash-note">Not connected</span></div><div className="dash-row"><span>Server load</span><span className="dash-note">Unavailable · GHOST-1</span></div><div className="dash-row"><span>Storage used</span><span className="dash-note">Unavailable · BUCKET-1</span></div><div className="dash-actions"><a className="dash-button primary" href="/admin">Open the window</a><a className="dash-button" href="/admin">Proof report</a></div></section>
    </div>
    <section className="dash-card" style={{marginTop:18}}><h2>Stopped by the pause</h2>{view.refused.length ? view.refused.map((row,i) => <p className="dash-note" key={i}>{row.task} · {row.path} · {row.at}</p>) : <p className="dash-empty">No recorded refusals.</p>}</section>
    {squads}
    <p className="dash-footer">Live measurements only. Unavailable sources stay empty. Controls apply to this server.</p>
  </div>;
}
