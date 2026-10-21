"use client";
import { useRef, useState } from "react";

type Preview = { token: string; items: { id: string; version: string }[] };

export function ApproveAllReady({ onApproved, className }: { onApproved?: () => Promise<void>; className?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function request(confirm: boolean) {
    setBusy(true);
    setMessage("");
    try {
      const res = await fetch("/api/skala", {method: "POST", headers: {"content-type": "application/json"},
        body: JSON.stringify({ action: confirm ? "bulk-confirm" : "bulk-preview", token: preview?.token, confirmed: confirm })});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Approval could not be confirmed. Reload the list.");
      if (confirm) {
        dialog.current?.close();
        setPreview(null);
        setMessage(`${data.approved.length} versions approved. Each approval was recorded.`);
        await onApproved?.();
      } else {
        setPreview(data);
        dialog.current?.showModal();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Approval could not be reached.");
      dialog.current?.close();
      setPreview(null);
    } finally { setBusy(false); }
  }
  return <div className="sk-bulk">
    <button className={className} type="button" disabled={busy} onClick={() => request(false)}>{busy ? "Checking…" : "Approve all ready"}</button>
    {message ? <p role="status">{message}</p> : null}
    <dialog ref={dialog} className="sk-dialog" aria-label="Confirm ready versions">
      <h2>Approve these versions?</h2>
      <p>Room-authored skills need individual source review and are excluded.</p>
      {preview?.items.length ? <ul className="sk-bulk-list">{preview.items.map(item => <li key={item.id}>{item.id} · {item.version}</li>)}</ul> : <p>No versions are ready.</p>}
      <button type="button" disabled={busy || !preview?.items.length} onClick={() => request(true)}>Confirm listed approvals</button>{" "}
      <button type="button" disabled={busy} onClick={() => { dialog.current?.close(); setPreview(null); }}>Cancel</button>
    </dialog>
  </div>;
}
