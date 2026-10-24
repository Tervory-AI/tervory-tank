import { notFound } from "next/navigation";
import { getMatch } from "../store";

/** Public watch page. Unpublished matches return 404. */
export default async function MootWatchPage({ params }: { params: Promise<{ match: string }> }) {
  const { match: matchId } = await params;
  const row = getMatch(matchId);
  if (!row || !row.published) notFound();

  return (
    <main className="moot-watch" style={{ maxWidth: 720, margin: "2rem auto", padding: "0 1rem", fontFamily: "Georgia, serif" }}>
      <h1>{row.title}</h1>
      <p>Public watch page (text edition). Nothing spoken here — that is later work.</p>
      <section>
        <h2>Judgment</h2>
        <p>Order: {row.judgmentOrder}</p>
      </section>
      <section>
        <h2>Fairness check</h2>
        <p>{row.fairnessReading}</p>
      </section>
      <section>
        <h2>What the court actually held</h2>
        <p>{row.reveal}</p>
      </section>
    </main>
  );
}
