"use client";

import { useCallback, useEffect, useState } from "react";

type Row = {
  task_type: string; rung: number; model: string; candidate_model: string | null; shadow_rate: number | string;
  previous_model: string | null; eval_threshold: number | string; cache_scope: string;
  n: number; agreement: number | string | null; cand_cost: number | string | null; prim_cost: number | string | null;
  calls_30d: number; cost_30d: number | string; cache_hits: number; eligible: boolean; saving_pct: number | null;
};
type Evals = { task_type: string; cases: number; accepted: number; rejected: number; manual: number };

const MODELS = ["haiku", "sonnet", "opus"];
const n = (v: number | string | null | undefined) => (v == null ? null : Number(v));
const money = (v: number | string | null | undefined) => { const x = n(v); return x == null ? "—" : `$${x.toFixed(x < 0.01 ? 5 : 2)}`; };

// Tank: the cost ladder. Each task type, the model it runs on, what is being tried in its shadow, and the promote button.
export default function TankPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [evals, setEvals] = useState<Evals[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/tank", { cache: "no-store" });
    const data = await res.json();
    if (res.ok) { setRows(data.ladder); setEvals(data.evals); } else setError(data.error ?? `HTTP ${res.status}`);
  }, []);
  useEffect(() => { refresh(); const id = setInterval(refresh, 15000); return () => clearInterval(id); }, [refresh]);

  async function act(task_type: string, action: string, extra: Record<string, unknown> = {}) {
    setBusy(task_type); setError(null);
    try {
      const res = await fetch("/api/tank", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ task_type, action, ...extra }) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      await refresh();
    } catch (err) { setError(err instanceof Error ? err.message : "Something went wrong"); } finally { setBusy(null); }
  }

  const spend = rows.reduce((a, r) => a + (n(r.cost_30d) ?? 0), 0);
  const calls = rows.reduce((a, r) => a + Number(r.calls_30d), 0);
  const hits = rows.reduce((a, r) => a + Number(r.cache_hits), 0);
  const evalsFor = (t: string) => evals.find((e) => e.task_type === t);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Tank</h1>
          <p className="sub">The cost ladder. A candidate runs in the shadow of the current model; when it agrees often enough, you promote it. Nothing moves without your click.</p>
        </div>
      </div>
      <div className="tiles">
        <div className="tile"><b>{calls.toLocaleString()}</b><span>calls · 30 days</span></div>
        <div className="tile"><b>{money(spend)}</b><span>model spend · 30 days</span></div>
        <div className="tile"><b>{hits.toLocaleString()}</b><span>answered from cache (rung 4)</span></div>
        <div className="tile"><b>{rows.filter((r) => r.candidate_model).length}</b><span>candidates in shadow</span></div>
      </div>
      {error && <p className="err">{error}</p>}

      <div className="rows" style={{ marginTop: 16 }}>
        {rows.map((r) => {
          const agr = n(r.agreement); const thr = n(r.eval_threshold) ?? 0.95; const ev = evalsFor(r.task_type);
          return (
            <div key={r.task_type} className="row" style={{ gridTemplateColumns: "1fr" }}>
              <div className="ladder-row">
                <div className="ladder-name">
                  <b>{r.task_type}</b>
                  <span className="muted" style={{ fontSize: 13 }}>{Number(r.calls_30d).toLocaleString()} calls · {money(r.cost_30d)}{r.cache_hits ? ` · ${r.cache_hits} cached` : ""}{ev ? ` · ${ev.cases} golden cases` : ""}</span>
                </div>
                <div className="ladder-model"><span className={`chip rung-${r.rung}`}>rung {r.rung}</span> <b>{r.model}</b>{r.previous_model && <span className="muted"> (was {r.previous_model})</span>}</div>
                <div className="ladder-cand">
                  {r.candidate_model ? (
                    <>
                      <span>→ <b>{r.candidate_model}</b> <span className="muted">{Math.round(Number(r.shadow_rate) * 100)}% shadow</span></span>
                      <span className="score" style={{ marginTop: 4 }}>
                        <span className="bar"><span className="fill" style={{ width: `${agr == null ? 0 : Math.round(agr * 100)}%`, background: agr != null && agr >= thr ? "var(--ok)" : "var(--warn)" }} /></span>
                        <span className="muted">{agr == null ? "no data" : `${Math.round(agr * 100)}% agree`} · {r.n}/30{r.saving_pct != null ? ` · saves ${r.saving_pct}%` : ""}</span>
                      </span>
                    </>
                  ) : (
                    <select defaultValue="" disabled={busy !== null} onChange={(e) => { if (e.target.value) act(r.task_type, "candidate", { candidate_model: e.target.value, shadow_rate: 1 }); }} aria-label="Candidate model">
                      <option value="">Try a cheaper model…</option>
                      {MODELS.filter((m) => m !== r.model).map((m) => <option key={m} value={m}>{m}</option>)}
                    </select>
                  )}
                </div>
                <div className="row-actions" style={{ padding: 0 }}>
                  {r.candidate_model && (
                    <>
                      <button type="button" className="sm" disabled={busy !== null || !r.eligible} title={r.eligible ? "" : "needs 30 scored runs at or above the gate"} onClick={() => act(r.task_type, "promote")}>Promote</button>
                      <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(r.task_type, "candidate", { candidate_model: null })}>Stop</button>
                    </>
                  )}
                  {!r.candidate_model && r.previous_model && (
                    <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(r.task_type, "rollback")}>Roll back</button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {rows.length === 0 && !error && <div className="row" style={{ padding: 14 }}><span className="muted">Loading…</span></div>}
      </div>
      <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
        Gate = the task type&apos;s eval threshold, over at least 30 scored shadow runs. Shadow spend is logged under Tervory&apos;s own tenant, never a client&apos;s.
      </p>
    </>
  );
}
