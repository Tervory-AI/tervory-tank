import { notFound, redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { marketLabRequest, type MarketDocument } from "@/lib/tank";
import "../../market-lab.css";

export const dynamic = "force-dynamic";

export default async function SourcePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ row?: string }> }) {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const { id } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) notFound();
  const query = await searchParams;
  const row = Number(query.row ?? 0);
  const offset = Number.isSafeInteger(row) && row >= 0 && row <= 10000000 ? Math.floor(row / 200) * 200 : 0;
  let source: MarketDocument;
  try {
    source = await marketLabRequest<MarketDocument>(tenant.tenantId, "document", { document_id: id, offset });
  } catch {
    return <main className="ml ml-source"><div className="ml-body"><a href="/market-lab">Back to Market Lab</a><h1>Source unavailable</h1><p>This source could not be read in your workspace. Try again shortly.</p></div></main>;
  }
  return <main className="ml ml-source"><div className="ml-body">
    <a href="/market-lab">Back to Market Lab</a>
    <h1>{source.name}</h1>
    <p>Stored on {source.fetched_at}. This document preserves the observations collected in that refresh. Counts may be calculated from the source records.</p>
    <p>{source.licence}</p>
    <h2>Source downloads</h2>
    <ul>{source.downloads.map((download, index) => <li key={`${download.url}-${index}`}><a href={download.url} rel="noreferrer" target="_blank">{download.url}</a></li>)}</ul>
    {source.points.length ? <><h2>Stored observations</h2><table>
      <thead><tr><th scope="col">Observation</th><th scope="col">Area</th><th scope="col">Date</th><th scope="col">Value</th><th scope="col">Unit</th></tr></thead>
      <tbody>{source.points.map((point, index) => <tr id={`point-${index + source.offset}`} key={index}>
        <th scope="row">{point.title}{point.withdrawn ? " — withdrawn from answers" : ""}</th><td>{point.geo}</td><td>{point.date}</td><td>{point.value}</td><td>{point.unit}</td>
      </tr>)}</tbody>
    </table></> : null}
    {source.events.length ? <><h2>Stored notices</h2>{source.events.map((event, index) => <article id={`event-${index + source.offset}`} key={index}>
      <h3>{event.title}</h3><p>{event.date}</p><p>{event.kind === "changed" ? "The linked page was checked for changes. Its text is not stored." : event.body}</p>
      {event.url.startsWith("https://") ? <a href={event.url} rel="noreferrer" target="_blank">Original notice</a> : null}
    </article>)}</> : null}
    <nav aria-label="Source pages">
      {offset > 0 ? <a href={`?row=${Math.max(0, offset - 200)}`}>Previous observations</a> : null}{" "}
      {offset + 200 < Math.max(source.point_count, source.event_count) ? <a href={`?row=${offset + 200}`}>More observations</a> : null}
    </nav>
  </div></main>;
}
