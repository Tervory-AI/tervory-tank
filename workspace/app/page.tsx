import { currentUser } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { loadDashboardData } from "./dashboard-data";
import { DashboardGreeting } from "./dashboard-local-data";
import "./dashboard.css";

async function ask(form: FormData) {
  "use server";
  const request = String(form.get("request") ?? "").trim();
  if (!request) return;
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  redirect(`/chats?${new URLSearchParams({ ask: request.slice(0, 20000) })}`);
}

export default async function DashboardPage() {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const user = await currentUser();
  if (!user?.firstName?.trim() || !tenant.orgName.trim()) {
    throw new Error("Dashboard identity data is unavailable.");
  }
  const data = await loadDashboardData(tenant);

  return <div className="client-dashboard">
    <aside className="client-dashboard-sidebar">
      <div className="client-dashboard-logo">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory AI" width={180} height={33} />
      </div>
      {[["/", "Home"], ["/chats", "Chats"], ["/data", "Files"], ["/billing", "Billing"], ["/onboarding", "Settings"]].map(([href, label]) =>
        <a key={label} href={href} aria-current={href === "/" ? "page" : undefined}>{label}</a>
      )}
    </aside>
    <div className="client-dashboard-main">
      <header className="client-dashboard-header">
        <DashboardGreeting firstName={user.firstName} />
        <p>{tenant.orgName}</p>
      </header>
      <form className="client-dashboard-ask" action={ask}>
        <input name="request" aria-label="What do you need today?" placeholder="What do you need today?" maxLength={20000} required />
        <a className="client-dashboard-button" href="/data">Add a file</a>
        <button className="client-dashboard-button client-dashboard-primary" type="submit">Go</button>
      </form>
      <div className="client-dashboard-totals">
        <section className="client-dashboard-card client-dashboard-total">
          <p className="client-dashboard-label">Jobs done this month</p>
          <p className="client-dashboard-number"><a href="/tasks">{data.jobsDone}</a></p>
        </section>
        <section className="client-dashboard-card client-dashboard-total">
          <p className="client-dashboard-label">You saved</p>
          <p className="client-dashboard-number client-dashboard-saved">{data.saved}</p>
        </section>
      </div>
      <section className="client-dashboard-card client-dashboard-recent">
        <h2>Recent work</h2>
        {data.recent.length ? data.recent.map(job =>
          <a className="client-dashboard-job" key={job.id} href={`/tasks?task=${encodeURIComponent(job.id)}`}>
            <span className="client-dashboard-job-title">{job.title}</span>
            <span className={`client-dashboard-dot client-dashboard-dot-${job.status}`} aria-hidden="true" />
            <span className="client-dashboard-status">{job.label}</span>
          </a>
        ) : <p className="client-dashboard-empty">No work yet.</p>}
      </section>
      <section className="client-dashboard-card">
        <h2>Your team</h2>
        <div className="client-dashboard-team">
          {data.team.map(member =>
            <a className="client-dashboard-member" key={member.agent} href={member.href}>
              <p>{member.name}</p>
              <p>{member.description}</p>
            </a>
          )}
        </div>
      </section>
    </div>
  </div>;
}
