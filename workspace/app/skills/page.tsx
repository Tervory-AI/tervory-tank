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

const RUNG = ["", "Frontier model", "Owned small model", "Code", "Cache"];

// Skala: every skill package, its lifecycle state, and the two human controls — run the evals, approve.
export default function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, EvalResult>>({});
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/skills", { cache: "no-store" });
    const data = await res.json();
    if (res.ok) setSkills(data as Skill[]);
    else setError(data.error ?? `HTTP ${res.status}`);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  async function act(s: Skill, action: "evals" | "approve" | "retire") {
    const key = `${s.id}@${s.version}`;
    setBusy(key);
    setError(null);
    try {
      const res = await fetch("/api/skills", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: s.id, version: s.version, action }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      if (action === "evals") setResults((r) => ({ ...r, [key]: data as EvalResult }));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(null);
    }
  }

  const agents = Array.from(new Set(skills.map((s) => s.agent)));

  return (
    <>
      <h1>Skills</h1>
      <p style={{ color: "var(--muted)" }}>
        A skill is a versioned package in the repo. <b>Run evals</b> scores it against its golden cases; a pass moves it to
        staging. <b>Approve</b> is your sign-off — only approved versions run for clients.
      </p>
      {error && <p className="err">{error}</p>}
      {agents.map((agent) => (
        <section key={agent} style={{ marginTop: 24 }}>
          <h2>{agent}</h2>
          <table>
            <thead>
              <tr><th>Skill</th><th>Rung</th><th>State</th><th>Evals</th><th>Last score</th><th></th></tr>
            </thead>
            <tbody>
              {skills.filter((s) => s.agent === agent).map((s) => {
                const key = `${s.id}@${s.version}`;
                const r = results[key];
                const score = s.last_eval_score == null ? null : Number(s.last_eval_score);
                return (
                  <tr key={key} style={{ opacity: s.present ? 1 : 0.5 }}>
                    <td>
                      <b>{s.id}</b> <span style={{ color: "var(--muted)" }}>{s.version}</span>
                      <div style={{ fontSize: 13, color: "var(--muted)" }}>{s.description}</div>
                      {r && (
                        <div style={{ fontSize: 13, marginTop: 4 }}>
                          {r.passed}/{r.total} passed · gate {r.gate} · ${r.cost_usd.toFixed(5)}
                          {r.details.filter((d) => !d.passed).map((d) => (
                            <div key={d.case} className="err">✗ {d.name ?? `case ${d.case}`}: {d.why}</div>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>{s.rung} · {RUNG[s.rung]}</td>
                    <td><span className={`state ${s.state}`}>{s.state}</span></td>
                    <td>{s.cases} cases · ≥{Math.round(Number(s.eval_threshold) * 100)}%</td>
                    <td>{score == null ? "—" : `${Math.round(score * 100)}%`}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {s.state !== "retired" && (
                        <button type="button" className="sm" disabled={busy !== null} onClick={() => act(s, "evals")}>
                          {busy === key ? "Running…" : "Run evals"}
                        </button>
                      )}{" "}
                      {s.state === "staging" && (
                        <button type="button" className="sm" disabled={busy !== null} onClick={() => act(s, "approve")}>Approve</button>
                      )}{" "}
                      {s.state === "approved" && (
                        <button type="button" className="sm ghost" disabled={busy !== null} onClick={() => act(s, "retire")}>Retire</button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ))}
    </>
  );
}
