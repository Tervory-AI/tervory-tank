"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  DEMO_ADVISORIES,
  DEMO_ENFORCE,
  DEMO_INVENTORY,
  DEMO_TRIAGE,
  type AdvisoryItem,
  type EnforceAction,
  type TriageItem,
} from "@/lib/autumbra-fixtures";
import "../product.css";
import "./demo.css";

type Tab = "triage" | "inventory" | "advisories" | "enforce";

const severityColor: Record<string, string> = {
  critical: "#E80008",
  high: "#C45C00",
  medium: "#001840",
  low: "#526077",
};

export function AutumbraDemoPanel() {
  const [tab, setTab] = useState<Tab>("triage");
  const [triage, setTriage] = useState<TriageItem[]>(DEMO_TRIAGE);
  const [advisories, setAdvisories] = useState<AdvisoryItem[]>(DEMO_ADVISORIES);
  const [enforce, setEnforce] = useState<EnforceAction[]>(DEMO_ENFORCE);
  const [flash, setFlash] = useState<string | null>(null);

  const counts = useMemo(
    () => ({
      triage: triage.filter((t) => t.state !== "solved").length,
      inventory: DEMO_INVENTORY.length,
      advisories: advisories.filter((a) => a.state === "open" || a.state === "proposed").length,
      enforce: enforce.filter((e) => e.state === "proposed" || e.state === "dry_run").length,
    }),
    [triage, advisories, enforce],
  );

  function ping(message: string) {
    setFlash(message);
    window.setTimeout(() => setFlash(null), 3200);
  }

  function resolveTriage(id: string) {
    setTriage((rows) =>
      rows.map((row) => (row.id === id ? { ...row, state: "solved" as const } : row)),
    );
    ping("Verified in demo. Receipt kept on this board (fixture — not Tank).");
  }

  function dismissAdvisory(id: string) {
    setAdvisories((rows) =>
      rows.map((row) => (row.id === id ? { ...row, state: "dismissed" as const } : row)),
    );
    ping("Advisory dismissed in demo. Live console keeps founder audit.");
  }

  function proposeFromAdvisory(id: string) {
    setAdvisories((rows) =>
      rows.map((row) => (row.id === id ? { ...row, state: "proposed" as const } : row)),
    );
    const adv = advisories.find((a) => a.id === id);
    if (adv) {
      setEnforce((rows) => [
        {
          id: `enf-demo-${Date.now()}`,
          kind: "patch_brief",
          title: `Patch brief · ${adv.package} (${adv.cve})`,
          site: "dogfood",
          state: "proposed",
          plain: `Fixture Enforce action from ${adv.cve}. Autumbra would open a bump PR; it never merges.`,
        },
        ...rows,
      ]);
    }
    ping("Enforce action proposed from advisory (fixture).");
    setTab("enforce");
  }

  function runEnforce(id: string, tap: "raise" | "undo" | "dry_run") {
    setEnforce((rows) =>
      rows.map((row) => {
        if (row.id !== id) return row;
        if (tap === "dry_run") return { ...row, state: "dry_run" };
        if (tap === "raise") return { ...row, state: "up" };
        return { ...row, state: "undone" };
      }),
    );
    const messages = {
      dry_run: "Practice run complete. Nothing changed at the edge.",
      raise: "Shield marked up in demo. Live mode still needs founder + health pass.",
      undo: "Shield taken down in demo.",
    } as const;
    ping(messages[tap]);
  }

  return (
    <main className="aub-page aub-demo">
      <header className="aub-top">
        <div>
          <img src="/brand/tervory-logo.png" width={160} height={36} alt="Tervory" />
          <p className="aub-eyebrow">Autumbra demo · fixtures only</p>
          <h1>Console meat you can click.</h1>
          <p className="aub-lead">
            Triage, inventory, advisories, and Enforce — interactive with demo data. No sign-in, no live
            Hugging Face, no Tank keys. After you sign in as founder, the same shape lands on{" "}
            <code>/admin/autumbra</code> for your sites.
          </p>
          <div className="aub-cta">
            <Link className="aub-secondary" href="/autumbra">
              Back to product
            </Link>
            <Link className="aub-primary" href="/sign-in">
              Sign in for your console
            </Link>
          </div>
        </div>
      </header>

      <p className="aub-demo-banner" role="status">
        Fixture mode · zero-ingestion story intact · actions update this board only
      </p>
      {flash && (
        <p className="aub-demo-flash" role="status">
          {flash}
        </p>
      )}

      <nav className="aub-tabs" aria-label="Demo sections">
        {(
          [
            ["triage", `Triage (${counts.triage})`],
            ["inventory", `Inventory (${counts.inventory})`],
            ["advisories", `Advisories (${counts.advisories})`],
            ["enforce", `Enforce (${counts.enforce})`],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "aub-tab aub-tab-on" : "aub-tab"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "triage" && (
        <section aria-label="Triage">
          {triage.map((item) => (
            <article key={item.id} className="aub-row">
              <div className="aub-row-head">
                <h2>
                  {item.target} · {item.signal}
                </h2>
                <span className="aub-pill" style={{ borderColor: severityColor[item.severity] }}>
                  {item.severity} · {item.state.replaceAll("_", " ")}
                </span>
              </div>
              <p>{item.summary}</p>
              <p className="aub-meta">
                {new Date(item.created_at).toLocaleString("en-US", { timeZone: "America/Los_Angeles" })}{" "}
                America/Los_Angeles · ${item.cost_usd.toFixed(4)} · {item.steps.length} steps
              </p>
              <details>
                <summary>Investigation receipts</summary>
                <ol>
                  {item.steps.map((step) => (
                    <li key={step.ledger_id}>
                      <strong>{step.step.replaceAll("_", " ")}</strong> · <code>{step.ledger_id}</code> · $
                      {step.cost_usd.toFixed(4)}
                    </li>
                  ))}
                </ol>
              </details>
              {item.state !== "solved" && (
                <button type="button" className="aub-btn" onClick={() => resolveTriage(item.id)}>
                  Verify and remember
                </button>
              )}
            </article>
          ))}
        </section>
      )}

      {tab === "inventory" && (
        <section aria-label="Inventory">
          <p className="aub-meta" style={{ marginBottom: 16 }}>
            Fingerprints only — no source trees, no client files.
          </p>
          <div className="aub-table">
            <div className="aub-table-head">
              <span>Package</span>
              <span>Ecosystem</span>
              <span>Version</span>
              <span>Site</span>
              <span>Fingerprint</span>
            </div>
            {DEMO_INVENTORY.map((row) => (
              <div key={row.id} className="aub-table-row">
                <span>{row.name}</span>
                <span>{row.ecosystem}</span>
                <span>{row.version}</span>
                <span>{row.site}</span>
                <code>{row.fingerprint}</code>
              </div>
            ))}
          </div>
        </section>
      )}

      {tab === "advisories" && (
        <section aria-label="Advisories">
          {advisories.map((item) => (
            <article key={item.id} className="aub-row">
              <div className="aub-row-head">
                <h2>
                  {item.cve} · {item.package}
                </h2>
                <span className="aub-pill" style={{ borderColor: severityColor[item.severity] }}>
                  {item.severity} · {Math.round(item.confidence * 100)}% · {item.state}
                </span>
              </div>
              <p>{item.summary}</p>
              <div className="aub-actions">
                {(item.state === "open" || item.state === "proposed") && (
                  <button type="button" className="aub-btn" onClick={() => proposeFromAdvisory(item.id)}>
                    Propose Enforce action
                  </button>
                )}
                {item.state !== "dismissed" && (
                  <button type="button" className="aub-btn-secondary" onClick={() => dismissAdvisory(item.id)}>
                    Dismiss
                  </button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}

      {tab === "enforce" && (
        <section aria-label="Enforce">
          {enforce.map((item) => (
            <article key={item.id} className="aub-row">
              <div className="aub-row-head">
                <h2>
                  {item.title} · {item.site}
                </h2>
                <span className="aub-pill">{item.kind.replaceAll("_", " ")} · {item.state.replaceAll("_", " ")}</span>
              </div>
              <p>{item.plain}</p>
              {item.expression && (
                <details>
                  <summary>Exactly what would change</summary>
                  <code className="aub-rule">{item.expression}</code>
                </details>
              )}
              <div className="aub-actions">
                {(item.state === "proposed" || item.state === "dry_run") && (
                  <>
                    <button type="button" className="aub-btn-secondary" onClick={() => runEnforce(item.id, "dry_run")}>
                      Practice run
                    </button>
                    <button type="button" className="aub-btn" onClick={() => runEnforce(item.id, "raise")}>
                      Shield
                    </button>
                  </>
                )}
                {(item.state === "up" || item.state === "dry_run" || item.state === "proposed") && (
                  <button type="button" className="aub-btn-secondary" onClick={() => runEnforce(item.id, "undo")}>
                    Undo
                  </button>
                )}
              </div>
            </article>
          ))}
        </section>
      )}

      <p className="aub-note" style={{ marginTop: 40 }}>
        Demo data only. Autumbra Watch · Autumbra Enforce. Zero-ingestion. Product name Autumbra only.
      </p>
    </main>
  );
}
