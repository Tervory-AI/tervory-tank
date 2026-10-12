"use client";

import { Fragment, useCallback, useEffect, useState } from "react";

type Field = { value: unknown; source: string; confidence: number };
type Rec = {
  id: string; task_id: string | null; batch: string | null; raw: Record<string, unknown>;
  profile: Record<string, Field>; passes: Record<string, Record<string, unknown>>;
  confidence: number; status: "queued" | "running" | "done" | "failed"; error: string | null;
};

const SAMPLE = `name,address,city,state,zip,phone,website
Example Domain,123 Main St,Boston,MA,02110,,example.com`;

function v(f?: Field): string {
  if (!f || f.value == null || f.value === "") return "";
  if (Array.isArray(f.value)) return f.value.map(String).join(", ");
  if (typeof f.value === "object") {
    const vals = Object.values(f.value as Record<string, unknown>);
    return vals.every((x) => x == null || typeof x !== "object") ? vals.filter((x) => x != null && x !== "").map(String).join(", ") : JSON.stringify(f.value);
  }
  return String(f.value);
}

// Base: paste a batch of records, run passes 1-2, watch the profiles fill in.
export default function DataPage() {
  const [batch, setBatch] = useState("");
  const [csv, setCsv] = useState(SAMPLE);
  const [preview, setPreview] = useState(true);
  const [engine, setEngine] = useState("");
  const [engines, setEngines] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [records, setRecords] = useState<Rec[]>([]);
  const [open, setOpen] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/base", { cache: "no-store" });
    if (res.ok) setRecords((await res.json()) as Rec[]);
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => {
    fetch("/api/base?engines=1", { cache: "no-store" }).then(async (r) => { if (r.ok) setEngines((await r.json()) as string[]); }).catch(() => {});
  }, []);
  useEffect(() => {
    if (!records.some((r) => r.status === "queued" || r.status === "running")) return;
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [records, refresh]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/base", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ batch, csv, preview, engine: engine || null }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setBatch("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const done = records.filter((r) => r.status === "done");
  const withSite = done.filter((r) => v(r.profile.website)).length;
  const withEmail = done.filter((r) => v(r.profile.emails)).length;
  const ready = done.filter((r) => r.confidence >= 80).length;
  const review = done.filter((r) => r.confidence < 60).length;

  return (
    <>
      <h1>Data</h1>
      <p style={{ color: "var(--muted)" }}>
        Paste records as CSV (header row first: name, address, city, state, zip, phone, website — any you have). Base runs
        all seven passes: clean, match, find the site, scrape it, extract facts, contacts, socials, business data, the industry
        module, then verification and a 0–100 score. Pick an engine to feed it that industry&apos;s own list — the FFL engine
        reads the ATF licensee export as-is.
      </p>
      <form onSubmit={submit} className="task-form">
        <input value={batch} onChange={(e) => setBatch(e.target.value)} placeholder="Batch name, e.g. ATF sample 500" maxLength={120} disabled={busy} required />
        <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={8} disabled={busy} style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }} />
        <div className="task-form-row">
          <select value={engine} onChange={(e) => setEngine(e.target.value)} disabled={busy} aria-label="Industry engine">
            <option value="">No engine (generic records)</option>
            {engines.map((e) => <option key={e} value={e}>{e.toUpperCase()} engine</option>)}
          </select>
          <label style={{ color: "var(--muted)", fontSize: 13 }}>
            <input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} /> preview (allow unapproved skill versions)
          </label>
          <button type="submit" disabled={busy || !batch.trim() || !csv.trim()}>{busy ? "Queueing…" : "Run Base"}</button>
        </div>
        {error && <p className="err">{error}</p>}
      </form>

      {records.length > 0 && (
        <div className="tiles">
          <div className="tile"><b>{records.length}</b><span>records</span></div>
          <div className="tile"><b>{done.length}</b><span>enriched</span></div>
          <div className="tile"><b>{done.length ? Math.round((withSite / done.length) * 100) : 0}%</b><span>with a website</span></div>
          <div className="tile"><b>{done.length ? Math.round((withEmail / done.length) * 100) : 0}%</b><span>with an email</span></div>
          <div className="tile"><b>{ready}</b><span>ready (80+)</span></div>
          <div className="tile"><b>{review}</b><span>need review (&lt;60)</span></div>
        </div>
      )}

      <table>
        <thead>
          <tr><th>Name</th><th>City</th><th>Website</th><th>Emails</th><th>Decision maker</th><th>Segment</th><th>Tier</th><th>Conf.</th><th>Status</th></tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <Fragment key={r.id}>
              <tr onClick={() => setOpen(open === r.id ? null : r.id)} style={{ cursor: "pointer" }}>
                <td>{v(r.profile.name) || String(r.raw.name ?? "")}</td>
                <td>{v(r.profile.city)}{v(r.profile.state) ? `, ${v(r.profile.state)}` : ""}</td>
                <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v(r.profile.website)}</td>
                <td style={{ maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v(r.profile.emails)}</td>
                <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{v(r.profile.decision_maker)}</td>
                <td>{v(r.profile.ffl_segment) || v(r.profile.business_model)}</td>
                <td>{v(r.profile.tier)}</td>
                <td>{r.status === "done" ? r.confidence : ""}</td>
                <td><span className={`state ${r.status}`}>{r.status}</span></td>
              </tr>
              {open === r.id && (
                <tr>
                  <td colSpan={9}>
                    {r.error && <p className="err">{r.error}</p>}
                    <table>
                      <thead><tr><th>Field</th><th>Value</th><th>Source</th><th>Confidence</th></tr></thead>
                      <tbody>
                        {Object.entries(r.profile).map(([k, f]) => (
                          <tr key={k}><td>{k}</td><td style={{ whiteSpace: "pre-wrap" }}>{v(f)}</td><td>{f.source}</td><td>{f.confidence}</td></tr>
                        ))}
                      </tbody>
                    </table>
                    <div className="meta">passes: {JSON.stringify(r.passes)}</div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {records.length === 0 && <tr><td colSpan={9} style={{ color: "var(--muted)" }}>No records yet.</td></tr>}
        </tbody>
      </table>
    </>
  );
}
