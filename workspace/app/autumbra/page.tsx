import Link from "next/link";
import "./product.css";

export const dynamic = "force-static";

export default function AutumbraProductPage() {
  return (
    <main className="aub-page">
      <header className="aub-top">
        <div>
          <img src="/brand/tervory-logo.png" width={160} height={36} alt="Tervory" />
          <p className="aub-eyebrow">Autumbra · protect.tervory.com</p>
          <h1>Watch finds it.<br />Enforce fixes it.<br />Your data never leaves.</h1>
          <p className="aub-lead">
            Autumbra is onsite first-line defence for your stack. Watch triages signals into a clear queue.
            Enforce proposes shields and patch briefs you approve. Nothing client-sensitive is ingested —
            we work on burned ThreatPayloads and inventory fingerprints, not your files or chats.
          </p>
          <div className="aub-cta">
            <Link className="aub-primary" href="/autumbra/demo">
              Open the live demo
            </Link>
            <Link className="aub-secondary" href="/sign-in">
              Sign in for your console
            </Link>
            <a className="aub-quiet" href="https://tervory.com">
              Tervory home
            </a>
          </div>
        </div>
      </header>

      <section className="aub-band" aria-label="Watch and Enforce">
        <article>
          <h2>Watch</h2>
          <p>
            Continuous triage across availability, certificates, headers, advisories, and inventory matches.
            You get a ranked queue with receipts — not a wall of raw logs. Practice mode shows exactly what
            Autumbra would do before anything is armed.
          </p>
        </article>
        <article>
          <h2>Enforce</h2>
          <p>
            Shields at the edge, patch-as-PR briefs for workers, and dry-run first. Autumbra never merges,
            never changes production keys, and never raises a shield when the site is already failing its
            health check. You tap; Autumbra keeps the proof.
          </p>
        </article>
      </section>

      <section className="aub-zero" aria-label="Zero ingestion">
        <h2>Zero-ingestion by design</h2>
        <p>
          Client documents, chat contents, and secrets stay on your side. Autumbra only handles burned
          ThreatPayloads, package fingerprints, and public check results. Dual-LLM air gap keeps untrusted
          text from reaching the side that can act. Hugging Face dogfood stays fixtures-only until you arm it.
        </p>
      </section>

      <section aria-label="What you get">
        <h2 style={{ fontSize: 22, fontWeight: 400, margin: "0 0 8px" }}>What you get after sign-in</h2>
        <p className="aub-note" style={{ marginBottom: 16 }}>
          Founder console · /admin/autumbra · same Autumbra product, your sites
        </p>
        <div className="aub-grid">
          <div className="aub-card">
            <h3>Triage queue</h3>
            <p>Open investigations with state, cost, and step receipts you can hand to a worker.</p>
          </div>
          <div className="aub-card">
            <h3>Inventory</h3>
            <p>Package and service fingerprints matched to advisories — no source upload required.</p>
          </div>
          <div className="aub-card">
            <h3>Advisories</h3>
            <p>Severity-ranked matches with confidence bars before anything is proposed.</p>
          </div>
          <div className="aub-card">
            <h3>Enforce actions</h3>
            <p>Shield dry-run, raise, undo, and patch briefs — all with ledger receipts.</p>
          </div>
        </div>
      </section>

      <section className="aub-after" aria-label="Try before sign-in">
        <h2>Try it without signing in</h2>
        <ul>
          <li>
            <Link href="/autumbra/demo">/autumbra/demo</Link> — interactive fixture console (triage, inventory,
            advisories, Enforce). Looks and acts real; no live HF or Tank keys required.
          </li>
          <li>
            After sign-in as founder: <code>/admin/autumbra</code> — your sites, live checks when Tank is up,
            same fixture board when the room is offline.
          </li>
        </ul>
      </section>

      <p className="aub-note">
        Product name: Autumbra. Roles: Watch · Enforce.
      </p>
    </main>
  );
}
