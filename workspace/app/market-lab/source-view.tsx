import type { MarketDocument } from "@/lib/tank";

/** Shared by the signed-in route and the isolated local fixture proof. */
export function SourceDocumentView({ source }: { source: MarketDocument }) {
  const offset = source.offset;
  return <main className="ml ml-source"><div className="ml-body">
    <a href="/market-lab">Back to Market Lab</a>
    <h1>{source.name}</h1>
    <p>Stored on {source.fetched_at}. This document preserves the observations collected in that refresh. Counts may be calculated from the source records.</p>
    <p>{source.licence}</p>
    <h2>Source downloads</h2>
    <ul>{source.downloads.map((download, index) => <li key={`${download.url}-${index}`}><a href={download.url} rel="noreferrer" target="_blank">{download.url}</a></li>)}</ul>
    {source.points.length ? <><h2>Stored observations</h2><div className="ml-source-table" role="region" aria-label="Stored observations" tabIndex={0}><table>
      <thead><tr><th scope="col">Observation</th><th scope="col">Area</th><th scope="col">Date</th><th scope="col">Value</th><th scope="col">Unit</th></tr></thead>
      <tbody>{source.points.map((point, index) => <tr id={`point-${index + source.offset}`} key={index}>
        <th scope="row">{point.title}{point.withdrawn ? " — withdrawn from answers" : ""}</th><td>{point.geo}</td><td>{point.date}</td><td>{point.value}</td><td>{point.unit}</td>
      </tr>)}</tbody>
    </table></div></> : null}
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
