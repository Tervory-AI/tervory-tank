import type { MarketDocument } from "@/lib/tank";
import { WarningEvidence } from "./warning-evidence";
import { formatRefreshed } from "./format";

/** Shared by the signed-in route and the isolated local fixture proof. */
export function SourceDocumentView({ source }: { source: MarketDocument }) {
  if (source.calculation) return <WarningEvidence source={source} />;
  const offset = source.offset;
  return <main className="ml ml-source"><div className="ml-body">
    <a href="/market-lab">Back to Market Lab</a>
    <h1>{source.name}</h1>
    <p>Stored on {formatRefreshed(source.fetched_at)}. These are the figures and notices saved during that refresh.</p>
    {source.presentation?.publisher ? <p>Source: {source.presentation.publisher_url ? <a href={source.presentation.publisher_url} rel="noreferrer" target="_blank">{source.presentation.publisher}</a> : source.presentation.publisher}.</p> : null}
    {source.presentation?.notice ? <p>{source.presentation.notice}{source.presentation.notice.includes("Creative Commons") ? <> <a href="https://creativecommons.org/licenses/by/4.0/" rel="noreferrer" target="_blank">Read the reuse licence</a>.</> : null}</p> : null}
    {source.presentation?.explanation ? <p>{source.presentation.explanation}</p> : null}
    {source.downloads.length ? <><h2>Source downloads</h2>
    <ul>{source.downloads.map((download, index) => <li key={`${download.url}-${index}`}><a href={download.url} rel="noreferrer" target="_blank">Download original data ({new URL(download.url).hostname})</a></li>)}</ul></> : null}
    {source.points.length ? <><h2>Stored observations</h2>
    {source.points.some((point) => point.revision_label) ? <p>For each date, Current figure is the latest version in this saved document. Earlier figures are labelled with the source’s version.</p> : null}
    <div className="ml-source-table" role="region" aria-label="Stored observations" tabIndex={0}><table>
      <thead><tr><th scope="col">Observation</th><th scope="col">Area</th><th scope="col">Period</th><th scope="col">Value</th><th scope="col">Unit</th></tr></thead>
      <tbody>{source.points.map((point, index) => <tr id={`point-${index + source.offset}`} key={index}>
        <th scope="row">{point.display_title}{point.withdrawn ? " — not used in answers" : ""}</th><td>{point.geo_name}</td><td>{point.date_label}</td>
        <td><span className="ml-source-value">{point.display_value ?? point.value}</span>{point.revision_label ? <small className="ml-source-revision">{point.revision_label}</small> : null}</td><td>{point.unit_label}</td>
      </tr>)}</tbody>
    </table></div></> : null}
    {source.events.length ? <><h2>Stored notices</h2>{source.events.map((event, index) => <article id={`event-${index + source.offset}`} key={index}>
      <h3>{event.display_title}</h3><p>{event.date_label}</p>{event.kind === "changed" ? <p>The linked page was checked for changes. Its text is not stored.</p> : event.body ? <details><summary>Publisher’s original wording</summary><p>{event.body}</p></details> : null}
      {event.display_url.startsWith("https://") ? <a href={event.display_url} rel="noreferrer" target="_blank">{event.link_label}</a> : null}
    </article>)}</> : null}
    <nav aria-label="Source pages">
      {offset > 0 ? <a href={`?row=${Math.max(0, offset - 200)}`}>Previous observations</a> : null}{" "}
      {offset + 200 < Math.max(source.point_count, source.event_count) ? <a href={`?row=${offset + 200}`}>More observations</a> : null}
    </nav>
  </div></main>;
}
