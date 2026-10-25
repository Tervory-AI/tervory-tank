import Link from "next/link";
import "./public.css";
import { PUBLIC_AUTUMBRA_FIXTURE } from "./fixtures";

export const dynamic = "force-dynamic";

/** Public Autumbra product page — no Clerk. Founder console stays at /admin/autumbra. */
export default function AutumbraPublicPage() {
  const f = PUBLIC_AUTUMBRA_FIXTURE;
  return (
    <main className="autumbra-public">
      <header className="autumbra-public-head">
        <img src="/brand/tervory-logo.png" width="160" height="36" alt="Tervory" />
        <p className="autumbra-public-eyebrow">Autumbra</p>
        <h1>Watch the edge.<br />Keep the proof.</h1>
        <p className="autumbra-public-lede">
          Autumbra Watch finds availability, DNS, certificate, and header problems across your Tervory
          products. Autumbra Enforce proposes recoveries for a founder to approve — never silent auto-fix
          from this page.
        </p>
      </header>


      <section className="autumbra-public-grid" aria-label="Autumbra Watch monitoring">
        <article>
          <h2>On watch</h2>
          <p>{f.monitor.running ? "Public checks are running on a five-minute cycle." : "Monitoring has not completed a cycle."}</p>
          <span>{f.monitor.unavailable_checks} unavailable checks</span>
        </article>
        <article>
          <h2>Look targets</h2>
          <ul>
            {f.lookTargets.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </article>
        <article>
          <h2>Open investigations</h2>
          <span className="autumbra-public-count">{f.investigations.length}</span>
          <ul>
            {f.investigations.map((item) => (
              <li key={item.id}>
                <strong>{item.target}</strong> · {item.signal}
                <p>{item.summary}</p>
              </li>
            ))}
          </ul>
        </article>
      </section>

      <section className="autumbra-public-threats" aria-label="ThreatPayload receipts">
        <h2>ThreatPayload receipts</h2>
        <p>
          Validated <code>ghost.threat.v1</code> payloads may propose a shield or handoff. Burn-on-fail —
          nothing reaches Enforce without a clean payload. Propose-only on this surface.
        </p>
        <ul>
          {f.threatReceipts.map((r) => (
            <li key={r.id}>
              <div>
                <strong>{r.action.replaceAll("_", " ")}</strong>
                <span className="autumbra-public-pill">{r.status.replaceAll("_", " ")}</span>
              </div>
              <p>{r.summary}</p>
              <p className="autumbra-public-meta">
                {r.schema_version} · {r.target} · {r.severity}
                {r.cve_ids?.length ? ` · ${r.cve_ids.join(", ")}` : ""}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section className="autumbra-public-roles">
        <h2>Watch and Enforce</h2>
        <div>
          <article>
            <h3>Autumbra Watch</h3>
            <p>Inventory, advisories, Look investigations, and ThreatPayload receipts. Evidence first.</p>
          </article>
          <article>
            <h3>Autumbra Enforce</h3>
            <p>Founder-gated proposals only. No keys, merges, or production changes from an unattended path.</p>
          </article>
        </div>
      </section>

      <footer className="autumbra-public-foot">
        <p>Founder console (private): <Link href="/admin/autumbra">/admin/autumbra</Link></p>
      </footer>
    </main>
  );
}
