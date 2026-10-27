"use client";

import { useState } from "react";

export function UndoButton({
  receiptId,
  tenantId,
  site,
  ruleId,
}: {
  receiptId: string;
  tenantId?: string;
  site?: string;
  ruleId?: string;
}) {
  const [status, setStatus] = useState<"idle" | "working" | "done" | "error">("idle");
  const [message, setMessage] = useState("");

  async function onUndo() {
    setStatus("working");
    setMessage("");
    try {
      const res = await fetch("/api/autumbra/undo", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          receipt_id: receiptId,
          tenant_id: tenantId || "",
          site: site || "coolify.tervory.com",
          rule_id: ruleId || "",
        }),
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
        disabled={status === "working" || status === "done"}
        style={{
          fontSize: "1.05rem",
          padding: "0.75rem 1.25rem",
          borderRadius: 8,
          border: "none",
          background: status === "done" ? "#1b7f4a" : "#111827",
          color: "white",
          cursor: status === "working" || status === "done" ? "default" : "pointer",
        }}
      >
        {status === "working" ? "Undoing…" : status === "done" ? "Undone" : "Undo this shield"}
      </button>
      {message ? (
        <p style={{ marginTop: "0.75rem", color: status === "error" ? "#b91c1c" : "#14532d" }}>
          {message}
        </p>
      ) : null}
    </div>
  );
}
