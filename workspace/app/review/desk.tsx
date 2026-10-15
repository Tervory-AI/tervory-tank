"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { ReviewItem } from "@/app/api/zenas/rules";

export function ReviewDesk({ items, note, reviewer }: { items: ReviewItem[]; note: string; reviewer: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function sign(event: React.FormEvent<HTMLFormElement>, item: ReviewItem) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const decision = form.get("decision") === "rejected" ? "rejected" : "approved";
    setBusy(true);
    setError(null);
    const res = await fetch(`/api/zenas/documents/${item.documentId}/reviews`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        decision,
        changes: String(form.get("changes") ?? ""),
        jurisdiction: item.jurisdiction,
      }),
    });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) {
      setError(typeof data.error === "string" ? data.error : "The sign-off was not recorded.");
      return;
    }
    router.refresh();
  }

  return (
    <>
      <p className="meta">Signed in as {reviewer}</p>
      {note && <p className="note">{note}</p>}
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="note">Nothing is waiting in your jurisdictions.</p>}
      {items.map((item) => (
        <article className="card" key={item.documentId}>
          <h2>{item.title}</h2>
          <p className="meta">{item.jurisdiction} · {item.area} · {item.state}</p>
          <div className="split">
            <section>
              <h2>Draft</h2>
              <p className="draft">{item.body}</p>
            </section>
            <section>
              <h2>Sources</h2>
              {item.sources.length === 0 && <p className="note">No sources were attached.</p>}
              {item.sources.map((source) => (
                <p key={source.citation}>
                  <span className="meta">{source.citation}</span><br />{source.quote}
                </p>
              ))}
              <h2>Worked matters</h2>
              {item.matches.length === 0 && <p className="note">No worked matter was matched.</p>}
              {item.matches.map((match) => (
                <div key={match.id}>
                  <p className="meta">{match.outcome || "outcome pending"} · {match.jurisdiction}</p>
                  {match.findings.map((finding) => <p key={finding}>{finding}</p>)}
                </div>
              ))}
            </section>
          </div>
          <form onSubmit={(event) => sign(event, item)}>
            <textarea name="changes" rows={4} placeholder="What you changed. Write none if you changed nothing." />
            <div className="actions">
              <button className="primary" disabled={busy} name="decision" value="approved" type="submit">Approve</button>
              <button className="secondary" disabled={busy} name="decision" value="rejected" type="submit">Reject</button>
            </div>
          </form>
        </article>
      ))}
    </>
  );
}
