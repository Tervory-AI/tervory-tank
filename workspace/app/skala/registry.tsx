"use client";

import { useCallback, useEffect, useState } from "react";
import { caseRecord, splitPackages, type EvalResult } from "./record";

type State = "candidate" | "staging" | "approved" | "retired";
export type Skill = {
  id: string; version: string; agent: string; rung: number; task_type: string | null; description: string;
  state: State; eval_threshold: number | string; cases: number; last_eval_score: number | string | null;
  last_eval_at: string | null; approved_by: string | null; present: boolean;
};

const RUNG: Record<number, string> = { 1: "model", 2: "owned", 3: "code", 4: "cache" };
export const AGENT_LABEL: Record<string, string> = { tier0: "Tier 0", base: "Base", orchestrator: "Orchestrator" };

function firstSentence(s: string): string {
  const m = s.replace(/^Pass \d[a-z]?[,.]?\s*/i, "").match(/^(.*?[.!?])(\s|$)/);
  return (m ? m[1] : s).slice(0, 110);
}

function matches(skill: Skill, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const hay = [skill.id, skill.version, skill.agent, skill.description, skill.state, skill.task_type ?? ""].join(" ").toLowerCase();
  return hay.includes(needle);
}

function EvalCases({ result }: { result: EvalResult }) {
  const shown = caseRecord(result);
  if (!shown.ok) return <p className="eval">{shown.message}</p>;
  return (
    <div className="eval">
      {shown.cases.map((item) => (
        <div key={item.key} className={item.passed ? undefined : "err"}>
          <p><b>{item.name}</b> — {item.passed ? "passed" : "failed"}</p>
          <p style={{ overflowWrap: "anywhere" }}>Goal: {item.goal}</p>
          <p style={{ overflowWrap: "anywhere" }}>Result: {item.result}</p>
        </div>
      ))}
      <p className="muted">Gate {result.gate} · ${result.cost_usd.toFixed(5)}</p>
    </div>
  );
}

// The skills registry. Approved versions are the ones that run for clients.
export function Registry({ query, section }: { query: string; section: string }) {
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

  const { main, archive } = splitPackages(skills);
  const visibleMain = main.filter((skill) => matches(skill, query) && (section === "skills" || section === skill.agent));
  const visibleArchive = archive.filter((skill) => matches(skill, query));
  const agents = Array.from(new Set(visibleMain.map((s) => s.agent)));
  const counts = {
    staging: skills.filter((s) => s.state === "staging").length,
    approved: skills.filter((s) => s.state === "approved").length,
    candidate: skills.filter((s) => s.state === "candidate").length,
  };
  const showArchive = section === "archive" || section === "skills";
  const showMain = section !== "archive";

  function rowsFor(list: Skill[]) {
    return list.map((s) => {
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
              <button type="button" className="sm primary" disabled={busy !== null} onClick={() => act(s, "approve")}>Approve</button>
            )}
            {s.state === "approved" && (
              <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(s, "retire")}>Retire</button>
            )}
          </span>
          {isOpen && (
            <div className="row-detail">
              {r ? <EvalCases result={r} /> : <p className="muted">Run evals to see each case, the goal, and the result.</p>}
            </div>
          )}
        </div>
      );
    });
  }

  const nothing = (showMain && agents.length === 0 && (!showArchive || visibleArchive.length === 0))
    || (section === "archive" && visibleArchive.length === 0);

  return (
    <div className="registry">
      <div className="page-head">
        <div>
          <p className="sub">
            {skills.length} packages · {counts.approved} approved · {counts.staging} staging · {counts.candidate} candidate.
            Approve is your sign-off: only approved versions run for clients.
          </p>
        </div>
        {counts.staging > 0 && section !== "archive" && (
          <button type="button" className="primary" disabled={busy !== null} onClick={approveAll}>
            {busy === "all" ? "Approving…" : `Approve all ${counts.staging} staging`}
          </button>
        )}
      </div>
      {error && <p className="err">{error}</p>}
      {nothing && <p className="muted">{query.trim() ? "No skill matches that." : "No packages in this list."}</p>}

      {showMain && agents.map((agent) => (
        <section key={agent} className="group">
          <h2 className="group-title">{AGENT_LABEL[agent] ?? agent}</h2>
          <div className="rows">
            {rowsFor(visibleMain.filter((s) => s.agent === agent))}
          </div>
        </section>
      ))}

      {showArchive && visibleArchive.length > 0 && (
        <section className="group">
          <h2 className="group-title">Archive</h2>
          <div className="rows">
            {rowsFor(visibleArchive)}
          </div>
        </section>
      )}
    </div>
  );
}
