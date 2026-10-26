import type { Metadata } from "next";
import Link from "next/link";
import { listPublishedMatches } from "./store";
import "./moot-watch.css";

export const metadata: Metadata = {
  title: "Moot Court · Zenas",
  description: "Public Moot watch — text edition. Training only; nothing here is a filed matter.",
};

/** Public Moot index on zenas.tervory.com (product host). Own shell — no workspace sidebar. */
export default function MootIndexPage() {
  const rows = listPublishedMatches();
  return (
    <main className="moot-watch" aria-label="Moot Court">
      <header className="moot-brand">
        <Link href="/zenas" className="moot-brand-link" aria-label="Zenas panel">
          <img src="/brand/zenas-on-dark.png" alt="Zenas" width={197} height={70} />
        </Link>
        <Link href="/zenas" className="moot-panel-link">Open Zenas panel</Link>
      </header>
      <h1>Moot Court</h1>
      <p>
        This is where Zenas trains in text. Public watch pages only — nothing spoken here yet.
        Law students will use it later, for free.
      </p>
      <section aria-label="Published matches">
        <h2>Published matches</h2>
        {rows.length === 0 ? (
          <p>No published matches yet.</p>
        ) : (
          <ul>
            {rows.map((row) => (
              <li key={row.matchId}>
                <Link href={`/moot/${row.matchId}`}>{row.title}</Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
