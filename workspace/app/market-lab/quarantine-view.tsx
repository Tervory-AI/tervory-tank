import { releaseBatch, rejectBatch, removeBatch } from "./quarantine-actions";
import { quarantineActions, type QuarantineBatch } from "./quarantine";

const ACTIONS = {
  Release: releaseBatch,
  Reject: rejectBatch,
  Remove: removeBatch,
} as const;

function BatchTable({ rows }: { rows: QuarantineBatch[] }) {
  if (!rows.length) return <p>None.</p>;
  return (
    <div className="ml-quarantine-scroll">
      <table>
        <thead>
          <tr>
            {["Series", "Source", "Region", "Currency", "Unit", "Fetched", "Why it is here", "Review"].map((heading) => (
              <th key={heading}>{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((batch) => (
            <tr key={batch.id}>
              <td>{batch.seriesId}</td>
              <td>{batch.source}</td>
              <td>{batch.region}</td>
              <td>{batch.currency}</td>
              <td>{batch.unit}</td>
              <td className="ml-mono">{batch.fetchedAt}</td>
              <td>{batch.reason || "Waiting for review"}</td>
              <td>
                {quarantineActions(batch.status).map((label) => (
                  <form key={label} action={ACTIONS[label]}>
                    <input type="hidden" name="batch" value={batch.id} />
                    <button className={label === "Release" ? "ml-primary" : ""} type="submit">
                      {label}
                    </button>
                  </form>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function QuarantinePanel({ batches }: { batches: QuarantineBatch[] }) {
  const held = batches.filter((batch) => batch.status === "held");
  const pooled = batches.filter((batch) => batch.status === "pooled");
  const closed = batches.filter((batch) => batch.status === "rejected" || batch.status === "removed");
  return (
    <section id="quarantine" className="ml-quarantine" aria-labelledby="quarantine-title">
      <h2 id="quarantine-title">Quarantine</h2>
      <p>A new batch waits here until it matches the series. Rejected batches stay out of the pool.</p>
      <h3>Waiting</h3>
      <BatchTable rows={held} />
      <h3>In the pool</h3>
      <p>Remove drops the batch from the pool. Gold from it is retired.</p>
      <BatchTable rows={pooled} />
      {closed.length ? (
        <>
          <h3>Closed</h3>
          <BatchTable rows={closed} />
        </>
      ) : null}
    </section>
  );
}
