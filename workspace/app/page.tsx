import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { createTask, readClientDashboard, type DashboardRead } from "@/lib/tank";
import "./control/dashboard.css";
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
  { name: "Tiger", slug: "tiger", job: "Price tracking" },
  { name: "Market Lab", slug: "market-lab", job: "Market research" },
  { name: "Zenas", slug: "zenas", job: "Legal research" },
];
const statuses: Record<string, string> = { queued: "Queued", running: "In progress", done: "Ready", failed: "Needs attention" };
export default async function DashboardPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const [user, params] = await Promise.all([currentUser(), searchParams]);
  let data: DashboardRead | null = null;
  try { data = await readClientDashboard(tenant.tenantId); } catch { /* Visible error below. */ }
  const savings = await readClientSavings().catch(() => null);
  return <div className="dashboard-root dash-client-root">
    <aside className="dash-sidebar" aria-label="Workspace"><img src="/brand/tervory-logo-reversed.png" alt="Tervory" />{[["/", "Home"], ["/tasks", "Chats"], ["/data", "Files"], ["/billing", "Billing"], ["/onboarding", "Settings"]].map(([href,label]) => <a key={label} href={href} aria-current={href === "/" ? "page" : undefined}>{label}</a>)}</aside>
    <div className="dash-client"><header className="dash-client-top"><h1>Hello{user?.firstName ? `, ${user.firstName}` : ""}</h1><span className="dash-note">{tenant.orgName}</span></header>
      <form className="dash-ask" action={ask}><input className="dash-input" name="request" aria-label="What do you need today?" placeholder="What do you need today?" maxLength={20000} required /><a className="dash-button" href="/data">Add a file</a><button className="dash-button primary" type="submit">Go</button></form>
      {params.error === "request" && <p role="alert" className="dash-problem">Your request could not be started. Please try again.</p>}
      {!data && <p role="alert" className="dash-problem">Your activity could not be loaded. Please refresh to try again.</p>}
      <div className="dash-client-kpis"><section className="dash-card"><p className="dash-label">Jobs done this month</p><p className="dash-value">{data?.jobs_done ?? "—"}</p></section><section className="dash-card"><p className="dash-label">You saved</p><p className="dash-value dash-good"><a className="savings-number" href="#your-savings">View savings</a></p><p className="dash-note">See the work behind every amount.</p></section><section className="dash-card"><p className="dash-label">Credits left</p><p className="dash-value">—</p><p className="dash-note">Your balance is not available yet.</p></section></div>
      <div id="your-savings"><SavingsLive initial={savings} loadReport={readClientSavings} loadRevision={readSavingsRevision} loadRows={readClientSavingsRows}/></div>
      <div className="dash-client-columns"><section className="dash-card"><h2>Waiting on you</h2><p className="dash-empty">Requests for your approval will appear here when connected.</p></section><section className="dash-card"><h2>Recent work</h2>{data?.recent?.length ? data.recent.map(job => <div className="dash-row" key={job.id}><a href="/tasks" style={{flex:1,color:"inherit",textDecoration:"none"}}>{job.title}</a><span className="dash-note">{statuses[job.status] ?? "In progress"}</span></div>) : <p className="dash-empty">{data ? "Your work will appear here after your first request." : "Your recent work is unavailable."}</p>}</section></div>
      <section className="dash-card"><h2>Your team</h2><div className="dash-team">{team.map(member => <a className="dash-member" key={member.slug} href={`/${member.slug}`}><div className="dash-member-logo"><img src={`/brand/${member.slug}-on-dark.png`} alt={member.name} /></div><span className="dash-note">{member.job}</span></a>)}</div></section>
    </div>
  </div>;
}
