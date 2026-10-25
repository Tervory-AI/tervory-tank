"use client";

import { useMemo, useState } from "react";

const FINDINGS = [
  { id: "f1", severity: "High", file: "workers/ingest.py", title: "Token logged on retry path", detail: "A retry branch writes the Authorization header into the worker log. Strip the header before the log call." },
  { id: "f2", severity: "Medium", file: "package-lock.json", title: "Pinned dependency behind advisory", detail: "extract-zip sits on an advisory. Bump when the upstream patch lands; no live exploit path in this tree." },
  { id: "f3", severity: "Low", file: "app/settings.tsx", title: "Missing empty-state copy", detail: "Settings renders a blank card when vault is offline. Add a short offline line so the page never looks broken." },
];

export function RadixPublic() {
  const [sev, setSev] = useState<"All" | "High" | "Medium" | "Low">("All");
  const [open, setOpen] = useState(FINDINGS[0].id);
  const rows = useMemo(
    () => FINDINGS.filter((f) => sev === "All" || f.severity === sev),
    [sev],
  );
  const active = rows.find((f) => f.id === open) ?? rows[0] ?? FINDINGS[0];

  return (
    <main className="rx-public" aria-label="Radix">
      <header>
        <p className="rx-eyebrow">Radix</p>
        <h1>Findings</h1>
        <p className="rx-lede">Review the scan, open a finding, and keep the release brief honest before anything ships.</p>
      </header>
      <div className="rx-filters" role="group" aria-label="Severity">
        {(["All", "High", "Medium", "Low"] as const).map((s) => (
          <button key={s} type="button" aria-pressed={sev === s} onClick={() => { setSev(s); setOpen(FINDINGS.find((f) => s === "All" || f.severity === s)?.id ?? FINDINGS[0].id); }}>{s}</button>
        ))}
      </div>
      <div className="rx-split">
        <ul>
          {rows.map((f) => (
            <li key={f.id}>
              <button type="button" className={open === f.id ? "on" : undefined} onClick={() => setOpen(f.id)}>
                <span data-sev={f.severity}>{f.severity}</span>
                <strong>{f.title}</strong>
                <em>{f.file}</em>
              </button>
            </li>
          ))}
        </ul>
        <article>
          <p className="rx-sev" data-sev={active.severity}>{active.severity}</p>
          <h2>{active.title}</h2>
          <p className="rx-file">{active.file}</p>
          <p>{active.detail}</p>
        </article>
      </div>
    </main>
  );
}
