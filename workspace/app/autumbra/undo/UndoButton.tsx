"use client";

import { useState } from "react";

export function UndoButton({
  receiptId,
  token,
}: {
  receiptId: string;
  token?: string;
}) {
  const [status, setStatus] = useState<"idle" | "working" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onUndo() {
    setStatus("working");
    setMessage("");
    const signed = (token || "").trim();
    if (!signed) {
      setStatus("error");
      setMessage("This undo link is invalid or has expired.");
      return;
    }
    try {
      const res = await fetch("/api/autumbra/undo", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ token: signed }),
      });
      const data = (await res.json()) as { ok?: boolean; detail?: string };
      if (!res.ok || !data.ok) {
        setStatus("error");
        setMessage(data.detail || "Something went wrong. Try again, or reply to your Autumbra email.");
        return;
      }
      setStatus("done");
      setMessage("Done. That shield is being removed.");
    } catch {
      setStatus("error");
      setMessage("Could not reach Autumbra. Try again in a moment.");
    }
  }

  return (
    <div style={{ marginTop: "1.5rem" }}>
      <button
        type="button"
        onClick={onUndo}
        disabled={status === "working" || status === "done" || !(token || "").trim()}
        style={{
          fontSize: "1.05rem",
          padding: "0.75rem 1.25rem",
          borderRadius: 8,
          border: "none",
          background: status === "done" ? "#1b7f4a" : "#111827",
          color: "white",
          cursor: status === "working" || status === "done" || !(token || "").trim() ? "default" : "pointer",
        }}
      >
        {status === "working" ? "Undoing…" : status === "done" ? "Undone" : "Undo this shield"}
      </button>
      {message ? (
        <p style={{ marginTop: "0.75rem", color: status === "error" ? "#b91c1c" : "#14532d" }}>
          {message}
        </p>
      ) : null}
      {!token ? (
        <p style={{ marginTop: "0.75rem", color: "#b91c1c" }}>
          This undo link is invalid or has expired. Use the Undo link from your Autumbra email.
        </p>
      ) : null}
      <p style={{ display: "none" }} aria-hidden data-receipt={receiptId} />
    </div>
  );
}
