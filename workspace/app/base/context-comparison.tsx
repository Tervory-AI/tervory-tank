import type { ContextReport } from "./context-report";

export function ContextComparison({ report }: { report?: ContextReport | null }) {
  return (
    <section className="bcp-section" id="context-trial">
      <h2>Company data trial</h2>
      <p className="bcp-copy">Context.dev suggestions stay beside Base’s answers. Only checked answers count toward accuracy.</p>
      {!report ? <p>Comparison could not load.</p> : !report.records ? (
        <p>No trial results yet. Selected public businesses can be compared once the trial key is set.</p>
      ) : (
        <>
          <p className="bcp-copy">Latest 200 records: {report.records} trial records. Credits per record: {report.creditsPerRecord?.toFixed(2) ?? "Not known"}.</p>
          {report.unknownCharges > 0 && <p>{report.unknownCharges} charges need confirmation.</p>}
          {report.fields.length === 0 ? <p>No checked answers yet.</p> : (
            <div className="bcp-table" role="table" aria-label="Company data comparison">
              <div className="bcp-tr bcp-context-cols bcp-th" role="row">
                {["Field", "Checked", "Base correct", "Context.dev correct"].map((label) => <span role="columnheader" key={label}>{label}</span>)}
              </div>
              {report.fields.map((row) => (
                <div className="bcp-tr bcp-context-cols" role="row" key={row.field}>
                  <span role="cell">{row.field}</span>
                  <span role="cell" data-label="Checked">{row.checked}</span>
                  <span role="cell" data-label="Base correct">{(100 * row.baseCorrect / row.checked).toFixed(1)}%</span>
                  <span role="cell" data-label="Context.dev correct">{(100 * row.contextCorrect / row.checked).toFixed(1)}%</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
