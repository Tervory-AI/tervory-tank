import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { readClientDashboard, type DashboardRead } from "@/lib/tank";
import "./control/dashboard.css";
import "./dashboard.css";
import { DashboardGreeting } from "./dashboard-greeting";
import { SavingsLive } from "./tank/proof/savings-set";
import { readClientSavings, readClientSavingsRows, readSavingsRevision } from "./tank/proof/savings-actions";

async function ask(form: FormData) {
  "use server";
  const request = String(form.get("request") ?? "").trim();
  if (!request) return;
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  redirect(`/chats?${new URLSearchParams({ ask: request.slice(0, 20000) })}`);
}
const team = [
  { name: "Base", slug: "base", job: "Business lists" },
  { name: "Tiger", slug: "tiger", job: "Prices" },
  { name: "Market Lab", slug: "market-lab", job: "Market research" },
  { name: "Zenas", slug: "zenas", job: "Legal" },
];
const statuses: Record<string, string> = { queued: "Queued", running: "In progress", done: "Ready", failed: "Failed" };
export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const [user, params] = await Promise.all([currentUser(), searchParams]);
  let data: DashboardRead | null = null;
  try { data = await readClientDashboard(tenant.tenantId); } catch { /* Visible error below. */ }
  const savings = await readClientSavings().catch(() => null);
  return <div className="dashboard-root dash-client-root">
    <div className="dash-client"><header className="dash-client-top"><DashboardGreeting firstName={user?.firstName} /><span className="dash-note">{tenant.orgName}</span></header>
      <form className="dash-ask" action={ask}><input className="dash-input" name="request" aria-label="What do you need today?" placeholder="What do you need today?" maxLength={20000} required /><a className="dash-button" href="/data">Add a file</a><button className="dash-button primary" type="submit">Go</button></form>
      {params.error === "request" && <p role="alert" className="dash-problem">Your request could not be started. Please try again.</p>}
      {!data && <p role="alert" className="dash-problem">Your activity could not be loaded. Please refresh to try again.</p>}
      <div className="dash-client-kpis"><section className="dash-card"><p className="dash-label">Jobs done this month</p><p className="dash-value">{data ? <a className="dashboard-source" href="/tasks">{data.jobs_done.toLocaleString("en-US")}</a> : "—"}</p></section><section className="dash-card"><p className="dash-label">You saved</p><p className="dash-value dash-good"><a className="savings-number" href="#your-savings">{savings ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(savings.month.saved)) : "—"}</a></p></section></div>
      <div className="dash-client-columns"><section className="dash-card"><h2>Recent work</h2>{data?.recent?.length ? data.recent.slice(0, 4).map(job => <div className="dash-row" key={job.id}><a href={`/tasks#task-${encodeURIComponent(job.id)}`} style={{flex:1,color:"inherit",textDecoration:"none"}}>{job.title}</a><span className={`dash-status dash-status-${job.status}`}><i aria-hidden="true" />{statuses[job.status] ?? "—"}</span></div>) : <p className="dash-empty">{data ? "No work yet." : "Your recent work is unavailable."}</p>}</section></div>
      <section className="dash-card"><h2>Your team</h2><div className="dash-team">{team.filter(member => data?.granted_squads?.includes(member.slug)).map(member => <a className="dash-member" key={member.slug} href={`/${member.slug}`}><strong>{member.name}</strong><span className="dash-note">{member.job}</span></a>)}</div></section>
      <div id="your-savings"><SavingsLive initial={savings} loadReport={readClientSavings} loadRevision={readSavingsRevision} loadRows={readClientSavingsRows}/></div>
    </div>
  </div>;
}
