"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { baseBatchStatus, uploadBaseCsv } from "./job-actions";
import { type BatchResult } from "./batch-data";
import { batchLabel } from "./model";

export function BatchWorkflow({ signedIn, selected, onSelect }: { signedIn: boolean; selected: string | null; onSelect: (batch: string) => void }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [result, setResult] = useState<BatchResult | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setUploadMessage("");
    try {
      const response = await uploadBaseCsv(data);
      if (!response.ok) { setUploadMessage(response.message); return; }
      onSelect(response.batch);
      setUploadMessage(`${response.rows} businesses received. Checking your list.`);
      form.reset();
      router.refresh();
    } catch { setUploadMessage("The upload could not be confirmed. Refresh your batches before trying again."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    setResult(null); setError("");
    if (!selected || !signedIn) return;
    const batch = selected;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const response = await baseBatchStatus(batch);
        if (stopped) return;
        if (!response.ok) { setError(response.message); return; }
        setResult(response.result);
        router.refresh();
        if (response.result.pending > 0) timer = setTimeout(poll, 5000);
      } catch { if (!stopped) setError("The results could not be loaded. Try again shortly."); }
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [selected, signedIn, reload, router]);

  return <div className="bcp-workflow">
    <h3>Upload a business list</h3>
    {signedIn ? <form className="bcp-upload" onSubmit={upload}>
      <label>List name <input className="bcp-input" name="name" maxLength={65} disabled={busy} /></label>
      <label>CSV file <input className="bcp-input" name="file" type="file" accept=".csv,text/csv" required disabled={busy} /></label>
      <button className="bcp-secondary" disabled={busy} type="submit">{busy ? "Uploading…" : "Upload and verify"}</button>
      <p className="bcp-copy">Include a name column. Website, phone, address, city, state and zip help match each business. Up to 1,000 rows and 500 KB.</p>
    </form> : <p className="bcp-copy">Sign in to your workspace to upload a list and download its results.</p>}
    {uploadMessage && <p role="status">{uploadMessage}</p>}
    {selected && signedIn && <section className="bcp-batch-result" aria-label="Batch results" aria-live="polite">
      <h3>{batchLabel(selected)}</h3>
      {error ? <div role="alert"><p>{error}</p><button className="bcp-secondary" type="button" onClick={() => setReload((value) => value + 1)}>Reload results</button></div>
        : !result ? <p>Loading results…</p> : <>
          <p className="bcp-copy">Rows in: {result.total} · Verified: {result.verified} · Failed checks: {result.failed} · Waiting: {result.pending}</p>
          {result.pending > 0 ? <p>Checking your list. Counts update automatically.</p>
            : result.verified > 0 ? <a className="bcp-secondary" href={`/base/download?batch=${encodeURIComponent(selected)}`}>Download verified CSV</a>
              : <p>No verified rows to download. Review the reasons below.</p>}
          <p className="bcp-copy">The download includes only finished rows with a recorded source, check date and no failed cross-checks. Other rows stay out of the verified CSV.</p>
          {result.reasons.length > 0 && <ul>{result.reasons.map(({ reason, count }) => <li key={reason}>{count} {count === 1 ? "row" : "rows"}: {reason}</li>)}</ul>}
          {result.total > result.rows.length && <p>Showing the first {result.rows.length} of {result.total} rows. The download includes every verified row.</p>}
          <ul className="bcp-list">{result.rows.map((row) => <li key={row.id} className="bcp-result-row">
            <p className="bcp-row-title">{row.name} · {row.status === "verified" ? "Verified" : row.status === "pending" ? "Waiting" : "Check failed"}</p>
            {row.reason && <p className="bcp-row-copy">{row.reason}</p>}
            {row.sourceUrl && row.checkedAt && <p className="bcp-row-copy"><a href={row.sourceUrl} target="_blank" rel="noopener noreferrer">{row.sourceUrl}</a> · Checked <time dateTime={row.checkedAt}>{row.checkedAt}</time></p>}
          </li>)}</ul>
        </>}
    </section>}
  </div>;
}
