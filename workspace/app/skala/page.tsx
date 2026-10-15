"use client";

import { useCallback, useEffect, useState } from "react";

type State = "candidate" | "staging" | "approved" | "retired";
type Skill = {
  id: string; version: string; agent: string; rung: number; task_type: string | null; description: string;
  state: State; eval_threshold: number | string; cases: number; last_eval_score: number | string | null;
  last_eval_at: string | null; approved_by: string | null; present: boolean;
};
type EvalResult = {
  skill: string; passed: number; total: number; score: number; threshold: number; cost_usd: number;
  state: State; gate: "passed" | "failed"; details: { case: number; name: string | null; passed: boolean; why: string }[];
};

const RUNG: Record<number, string> = { 1: "model", 2: "owned", 3: "code", 4: "cache" };
const AGENT_LABEL: Record<string, string> = { tier0: "Tier 0", base: "Base", orchestrator: "Orchestrator" };

function firstSentence(s: string): string {
  const m = s.replace(/^Pass \d[a-z]?[,.]?\s*/i, "").match(/^(.*?[.!?])(\s|$)/);
  return (m ? m[1] : s).slice(0, 110);
}

// Skala: every skill package, its lifecycle state, and the two human controls — run the evals, approve.
export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, EvalResult>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/skala", { cache: "no-store" });
    const data = await res.json();
    if (res.ok) setSkills(data as Skill[]);
    else setError(data.error ?? `HTTP ${res.status}`);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function act(s: Skill, action: "evals" | "approve" | "retire", quiet = false) {
    const key = `${s.id}@${s.version}`;
    if (!quiet) setBusy(key);
    setError(null);
    try {
      const res = await fetch("/api/skala", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: s.id, version: s.version, action }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      if (action === "evals") { setResults((r) => ({ ...r, [key]: data as EvalResult })); setOpen(key); }
      if (!quiet) await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      if (!quiet) setBusy(null);
    }
  }

  async function approveAll() {
    setBusy("all");
    for (const s of skills.filter((x) => x.state === "staging")) await act(s, "approve", true);
    await refresh();
    setBusy(null);
  }

  const agents = Array.from(new Set(skills.map((s) => s.agent)));
  const counts = { staging: skills.filter((s) => s.state === "staging").length, approved: skills.filter((s) => s.state === "approved").length,
    candidate: skills.filter((s) => s.state === "candidate").length };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Skala</h1>
          <p className="sub">
            {skills.length} packages · {counts.approved} approved · {counts.staging} staging · {counts.candidate} candidate.
            Approve is your sign-off: only approved versions run for clients.
          </p>
        </div>
        {counts.staging > 0 && (
          <button type="button" disabled={busy !== null} onClick={approveAll}>
            {busy === "all" ? "Approving…" : `Approve all ${counts.staging} staging`}
          </button>
        )}
      </div>
      {error && <p className="err">{error}</p>}

      {agents.map((agent) => (
        <section key={agent} className="group">
          <h2 className="group-title">{AGENT_LABEL[agent] ?? agent}</h2>
          <div className="rows">
            {skills.filter((s) => s.agent === agent).map((s) => {
              const key = `${s.id}@${s.version}`;
              const r = results[key];
              const score = s.last_eval_score == null ? null : Number(s.last_eval_score);
              const threshold = Number(s.eval_threshold);
              const isOpen = open === key;
              return (
                <div key={key} className={`row ${isOpen ? "open" : ""}`} style={{ opacity: s.present ? 1 : 0.5 }}>
                  <button type="button" className="row-main" onClick={() => setOpen(isOpen ? null : key)} aria-expanded={isOpen}>
                    <span className="row-name"><b>{s.id}</b> <span className="muted">{s.version}</span></span>
                    <span className="row-desc">{firstSentence(s.description)}</span>
                    <span className={`chip rung-${s.rung}`}>{RUNG[s.rung] ?? `rung ${s.rung}`}</span>
                    <span className={`state ${s.state}`}>{s.state}</span>
                    <span className="score" title={`${s.cases} cases · gate ≥${Math.round(threshold * 100)}%`}>
                      <span className="bar"><span className="fill" style={{ width: `${score == null ? 0 : Math.round(score * 100)}%`, background: score != null && score >= threshold ? "var(--ok)" : "var(--warn)" }} /></span>
                      <span className="muted">{score == null ? "—" : `${Math.round(score * 100)}%`}</span>
                    </span>
                  </button>
                  <span className="row-actions">
                    {s.state !== "retired" && (
                      <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(s, "evals")}>
                        {busy === key ? "Running…" : "Run evals"}
                      </button>
                    )}
                    {s.state === "staging" && (
                      <button type="button" className="sm" disabled={busy !== null} onClick={() => act(s, "approve")}>Approve</button>
                    )}
                    {s.state === "approved" && (
                      <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(s, "retire")}>Retire</button>
                    )}
                  </span>
                  {isOpen && (
                    <div className="row-detail">
                      <p>{s.description}</p>
                      <p className="muted">
                        {s.cases} golden cases · gate ≥{Math.round(threshold * 100)}%
                        {s.last_eval_at ? ` · last run ${new Date(s.last_eval_at).toLocaleString()}` : ""}
                        {s.approved_by ? " · approved" : ""}
                        {s.task_type ? ` · policy ${s.task_type}` : ""}
                      </p>
                      {r && (
                        <div className="eval">
                          <b>{r.passed}/{r.total} passed</b> · gate {r.gate} · ${r.cost_usd.toFixed(5)}
                          {r.details.filter((d) => !d.passed).map((d) => (
                            <div key={d.case} className="err">✗ {d.name ?? `case ${d.case}`}: {d.why}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </>
  );
}
