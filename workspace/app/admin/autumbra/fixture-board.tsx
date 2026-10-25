"use client";

import Link from "next/link";
import { useState } from "react";
import {
  DEMO_ADVISORIES,
  DEMO_ENFORCE,
  DEMO_INVENTORY,
  DEMO_TRIAGE,
  type EnforceAction,
} from "@/lib/autumbra-fixtures";

export function AutumbraFixtureBoard() {
  const [enforce, setEnforce] = useState<EnforceAction[]>(DEMO_ENFORCE);
  const [note, setNote] = useState<string | null>(null);

  function tap(id: string, next: EnforceAction["state"], message: string) {
    setEnforce((rows) => rows.map((row) => (row.id === id ? { ...row, state: next } : row)));
    setNote(message);
  }

  return (
    <section className="ghost-tile" aria-label="Fixture board" style={{ marginTop: 48 }}>
      <div className="ghost-section-title">
        <h2>Fixture board · Watch + Enforce meat</h2>
        <span>Works when Tank / HF are offline · same data as <Link href="/autumbra/demo">/autumbra/demo</Link></span>
      </div>
      {note && <p role="status" className="ghost-result">{note}</p>}

      <h3 style={{ fontSize: 17, fontWeight: 400 }}>Triage</h3>
      {DEMO_TRIAGE.map((item) => (
        <article key={item.id} className="ghost-issue">
          <div className="ghost-issue-head">
            <h2>
              {item.target} · {item.signal}
            </h2>
            <span className="ghost-state">
              {item.severity} · {item.state.replaceAll("_", " ")}
            </span>
          </div>
          <p>{item.summary}</p>
        </article>
      ))}

      <h3 style={{ fontSize: 17, fontWeight: 400, marginTop: 28 }}>Inventory</h3>
      <ul className="ghost-receipts">
        {DEMO_INVENTORY.map((row) => (
          <li key={row.id}>
            <strong>
              {row.name}@{row.version}
            </strong>
            <code>{row.fingerprint}</code>
            <span>{row.site}</span>
          </li>
        ))}
      </ul>

      <h3 style={{ fontSize: 17, fontWeight: 400, marginTop: 28 }}>Advisories</h3>
      {DEMO_ADVISORIES.map((item) => (
        <article key={item.id} className="ghost-issue">
          <div className="ghost-issue-head">
            <h2>
              {item.cve} · {item.package}
            </h2>
            <span className="ghost-state">
              {item.severity} · {Math.round(item.confidence * 100)}%
            </span>
          </div>
          <p>{item.summary}</p>
        </article>
      ))}

      <h3 style={{ fontSize: 17, fontWeight: 400, marginTop: 28 }}>Enforce actions</h3>
      {enforce.map((item) => (
        <article key={item.id} className="ghost-shield">
          <div className="ghost-issue-head">
            <h3>
              {item.title} · {item.site}
            </h3>
            <span className="ghost-state">{item.state.replaceAll("_", " ")}</span>
          </div>
          <p>{item.plain}</p>
          <div className="ghost-shield-actions">
            <button
              type="button"
              className="ghost-secondary"
              onClick={() => tap(item.id, "dry_run", "Practice run: nothing changed (fixture).")}
            >
              Practice run
            </button>
            <button type="button" onClick={() => tap(item.id, "up", "Shield marked up in fixture board.")}>
              Shield
            </button>
            <button
              type="button"
              className="ghost-secondary"
              onClick={() => tap(item.id, "undone", "Shield undone in fixture board.")}
            >
              Undo
            </button>
          </div>
        </article>
      ))}
    </section>
  );
}
