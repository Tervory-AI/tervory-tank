export type EvidenceRow = Record<string, string | number | boolean | null>;
type Pair = { primary_model: string; candidate_model: string; samples: number; agreement: number | null; primary_cost_usd: number; could_have_cost_usd: number };
export type TaskProof = { task_type: string; calls: number; priced_calls: number; actual_usd: number; baseline_usd: number; saved_usd: number; backfilled_calls: number; unpriced_calls: number; code_calls: number; code_share: number | null; shadow_pairs: Pair[] };
export type Proof = { tenant_id: string; region: string; tasks: TaskProof[]; ledger: EvidenceRow[]; shadows: EvidenceRow[]; runs: EvidenceRow[]; cases: EvidenceRow[]; promotions: EvidenceRow[]; policies: EvidenceRow[]; state: EvidenceRow[] };
const usd = (n: number) => `$${Number(n).toFixed(6)}`;
const percent = (n: number | null) => n === null ? "Not measured" : `${(Number(n) * 100).toFixed(1)}%`;
const url = (task: string, section: string) => `/tank/proof?task=${encodeURIComponent(task)}#${section}`;

function Evidence({ title, id, rows }: { title: string; id: string; rows: EvidenceRow[] }) {
  const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
  return <section id={id} className="proof-evidence"><h2>{title}</h2>
    {!rows.length ? <p>No rows recorded yet.</p> : <div className="proof-scroll" tabIndex={0} aria-label={`${title} table`}><table><thead><tr>{keys.map(key => <th key={key}>{key.replaceAll("_", " ")}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)} id={row.id ? `row-${row.id}` : undefined}>{keys.map(key => <td key={key}>{key === "ledger_id" && row[key] ? <a href={`#row-${row[key]}`}>{String(row[key])}</a> : key === "run_id" && row[key] ? <a href={`#row-${row[key]}`}>{String(row[key])}</a> : row[key] === null ? "—" : String(row[key] ?? "")}</td>)}</tr>)}</tbody></table></div>}
  </section>;
}

export function ProofView({ data, task }: { data: Proof; task?: string }) {
  const query = task ? `&task=${encodeURIComponent(task)}` : "";
  return <article className="proof">
    <header><div><a href="/tank">← Tank</a><p className="proof-kicker">Founder · {data.region} · platform evidence</p><h1>Tank proof</h1><p>What we tested, what it cost, and what we saved.</p></div>
      <nav aria-label="Export evidence"><a href={`/tank/proof/export?format=csv${query}`}>Export CSV</a><a href={`/tank/proof/export?format=pdf${query}`}>Export PDF</a></nav></header>
    <aside>Savings compare the same tokens at baseline prices with actual spend. Backfilled rows use the price book available when filled. Unknown prices are excluded. Bench and shadow spend stay separate. Zero-token cache hits claim no token savings.</aside>
    {task && <p><a href="/tank/proof">All tasks</a> / {task}</p>}
    {!data.tasks.length && <p>No evidence recorded yet.</p>}
    <div className="proof-cards">{data.tasks.map(row => <section key={row.task_type} className="proof-task"><h2><a href={url(row.task_type, "receipts")}>{row.task_type}</a></h2>
      <dl><div><dt>Money saved</dt><dd><a href={url(row.task_type,"receipts")}>{usd(row.saved_usd)}</a></dd></div>
        <div><dt>Baseline / actual</dt><dd><a href={url(row.task_type,"receipts")}>{usd(row.baseline_usd)} / {usd(row.actual_usd)}</a></dd></div>
        <div><dt>Calls served by code</dt><dd><a href={url(row.task_type,"receipts")}>{percent(row.code_share)} ({row.code_calls} / {row.calls})</a></dd></div>
        <div><dt>Receipt coverage</dt><dd><a href={url(row.task_type,"receipts")}>{row.priced_calls} priced · {row.backfilled_calls} backfilled · {row.unpriced_calls} unpriced</a></dd></div></dl>
      <p className="proof-links"><a href={url(row.task_type,"benchmarks")}>Tests and cost per call</a><a href={url(row.task_type,"promotions")}>Promotion dates</a></p>
      {row.shadow_pairs.map(pair => <div className="proof-pair" key={`${pair.primary_model}:${pair.candidate_model}`}><h3>{pair.primary_model} → {pair.candidate_model}</h3><p>Shadow comparison</p>
        <a href={url(row.task_type,"shadows")}>{pair.samples} pairs · {percent(pair.agreement)} agreement</a><p><a href={url(row.task_type,"shadows")}>Primary {usd(pair.primary_cost_usd)} · could have cost {usd(pair.could_have_cost_usd)}</a></p></div>)}
      {!row.shadow_pairs.length && <p>No shadow pairs recorded yet.</p>}
    </section>)}</div>
    <Evidence id="schedule" title="Benchmark status" rows={data.state}/>
    <Evidence id="policies" title="Current routes and baselines" rows={data.policies}/>
    <Evidence id="benchmarks" title="Tests and cost per call" rows={data.runs}/>
    <Evidence id="cases" title="Individual test receipts" rows={data.cases}/>
    <Evidence id="shadows" title="Shadow pairs" rows={data.shadows}/>
    <Evidence id="promotions" title="Promotion history" rows={data.promotions}/>
    <Evidence id="receipts" title="Ledger receipts" rows={data.ledger}/>
  </article>;
}
