import type { Metadata } from "next";
import Link from "next/link";
import { listPublishedMatches } from "./store";
import "./moot-watch.css";

export const metadata: Metadata = {
  title: "Moot Court · Zenas",
  description: "Public Moot watch — text edition. Training only; nothing here is a filed matter.",
};

/** Public Moot index on zenas.tervory.com (product host). */
export default function MootIndexPage() {
  const rows = listPublishedMatches();
  return (
    <main className="moot-watch" aria-label="Moot Court">
      <h1>Moot Court</h1>
      <p>
        This is where Zenas trains in text. Public watch pages only — nothing spoken here yet.
        Law students will use it later, for free.
      </p>
      <p>
        Full Zenas panel: <Link href="/zenas">zenas.tervory.com/zenas</Link>
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
