import { notFound } from "next/navigation";
import { WatchPanel } from "../WatchPanel";
import { getMatch } from "../store";
import "../moot-watch.css";

/** Public watch page. Unpublished matches return 404. */
export default async function MootWatchPage({ params }: { params: Promise<{ match: string }> }) {
  const { match: matchId } = await params;
  const result = await getMatch(matchId);
  if (result.status === "missing") notFound();
  if (result.status === "unavailable" || result.status === "malformed") {
    return <main className="moot-watch" aria-label="Moot watch">
      <p role="alert" data-moot-state={result.status}>Room unavailable</p>
    </main>;
  }
  return <WatchPanel row={result.match} />;
}
