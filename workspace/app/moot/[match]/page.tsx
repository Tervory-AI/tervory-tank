import { notFound } from "next/navigation";
import { WatchPanel } from "../WatchPanel";
import { getMatch } from "../store";
import "../moot-watch.css";

/** Public watch page. Unpublished matches return 404. */
export default async function MootWatchPage({ params }: { params: Promise<{ match: string }> }) {
  const { match: matchId } = await params;
  const row = getMatch(matchId);
  if (!row || !row.published) notFound();
  return <WatchPanel row={row} />;
}
