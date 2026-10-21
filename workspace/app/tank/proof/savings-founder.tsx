import { clerkClient } from "@clerk/nextjs/server";
import { tenantIdFor, uuidFrom } from "@/lib/tenant";
import { resolveTenantNames } from "./tenant-names";
import { proofResponse } from "./server";
import { readFounderSavingsRows } from "./savings-founder-actions";
import { EvidenceButton, SavingsSet } from "./savings-set";
import { dollars, type FounderSavings } from "./savings-types";

function Margin({ data }: { data: FounderSavings }) {
  const load = readFounderSavingsRows.bind(null, data.tenant_id);
  const evidence = (label: string, start?: string, until?: string) => <EvidenceButton label={label} filters={{end:data.as_of,population:"costs",start,until}} loadRows={load} founder/>;
  return <section className="savings-costs"><h2>Tervory’s margin · {data.tenant_id === "all" ? "all clients" : "selected client"}</h2>
    <p>Founder only. Payments have not been connected to verified amounts. Price-book rates alone do not prove what a client paid.</p>
    <dl><div><dt>Client paid</dt><dd>no billing data yet</dd></div><div><dt>Margin to date / percentage</dt><dd>no billing data yet</dd></div>
      <div><dt>Recorded work cost to date</dt><dd>{evidence(dollars(data.margin.total.actual))}</dd></div><div><dt>Recorded baseline to date</dt><dd>{evidence(dollars(data.margin.total.baseline))}</dd></div></dl>
    <p>{evidence(`${data.margin.total.unknown_costs} unknown costs · ${data.margin.total.unknown_baselines} unavailable baselines`)}. These sums cover live work on this box, including fees and flagged comparisons; they do not represent complete costs when amounts are unknown.</p>
    <details><summary>Daily costs and margin</summary><div className="savings-cost-days"><table><thead><tr><th>Day (UTC)</th><th>Paid</th><th>Actual cost</th><th>Baseline</th><th>Margin / %</th></tr></thead><tbody>{data.margin.daily.map(d => <tr key={d.day}><td>{d.day}</td><td>no billing data yet</td><td>{evidence(dollars(d.actual),`${d.day}T00:00:00Z`,new Date(Date.parse(d.day)+86400000).toISOString())}</td><td>{evidence(dollars(d.baseline),`${d.day}T00:00:00Z`,new Date(Date.parse(d.day)+86400000).toISOString())}</td><td>no billing data yet</td></tr>)}</tbody></table></div></details>
  </section>;
}
function ClientSet({ data, title }: { data: FounderSavings; title: string }) {
  const load = readFounderSavingsRows.bind(null, data.tenant_id);
  const query = new URLSearchParams({tenant_id:data.tenant_id,end:data.as_of});
  return <><SavingsSet data={data} title={title} loadRows={load}/><nav className="savings-exports" aria-label={`${title} savings exports`}><a href={`/tank/proof/savings-export?${query}&format=csv`}>Savings CSV</a><a href={`/tank/proof/savings-export?${query}&format=pdf`}>Savings PDF</a></nav>
    <p>Exports include all graph totals and the first 100 matching evidence rows. Use Browse evidence to export further pages with the same totals and cutoff.</p>
    <EvidenceButton label="Browse evidence and export pages" filters={{end:data.as_of}} loadRows={load} founder exportBase={`/tank/proof/savings-export?${query}`}/>
    <Margin data={data}/><section><h2>Rows left out of client savings</h2>{!data.excluded.length ? <p>No excluded rows.</p> : <><ul>{data.excluded.map(r => <li key={r.excluded_reason}><EvidenceButton label={`${r.excluded_reason}: ${r.count}`} filters={{end:data.as_of,population:"excluded"}} loadRows={load} founder/></li>)}</ul><EvidenceButton label="Inspect excluded rows" filters={{end:data.as_of,population:"excluded"}} loadRows={load} founder/></>}</section></>;
}
export async function FounderSavingsPanel({ tenant }: { tenant?: string }) {
  const all: FounderSavings = await (await proofResponse({},undefined,"/savings")).json();
  const names = await resolveTenantNames(all.tenants, async params => (await clerkClient()).organizations.getOrganizationList(params), tenantIdFor, uuidFrom);
  const selected = tenant && tenant!=="all" ? tenant : undefined;
  const one: FounderSavings | null = selected ? await (await proofResponse({tenant_id:selected,end:all.as_of},undefined,"/savings")).json() : null;
  return <article className="savings-founder"><a href="/tank">← Tank</a><p>Founder · {all.region}</p><h1>Client savings</h1><p>The same five graphs each client sees, using only defensible comparisons. Tervory is a separate choice below.</p>
    <ClientSet data={all} title="All clients"/>
    <form action="/tank/proof" method="get"><label>Client<select aria-label="Client" name="tenant_id" defaultValue={selected ?? "all"}><option value="all">Choose a client</option>{all.tenants.map(id => <option key={id} value={id}>{names.tenant_names[id]}</option>)}</select></label><button type="submit">Show client</button></form>
    {names.tenant_names_note && <p role="status">{names.tenant_names_note}</p>}
    {one && <ClientSet data={one} title={names.tenant_names[one.tenant_id] ?? "Unlinked account"}/>}
  </article>;
}
