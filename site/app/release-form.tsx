"use client";

import { useId, useState, type FormEvent } from "react";

type Status = "idle" | "saving" | "saved" | "failed";

export function ReleaseForm() {
  const fieldId = useId();
  const [status, setStatus] = useState<Status>("idle");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") || "");
    setStatus("saving");
    try {
      const response = await fetch("/api/release-notice", {
        method: "POST",
        headers: { accept: "application/json", "content-type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = (await response.json().catch(() => null)) as { stored?: boolean } | null;
      setStatus(response.ok && body?.stored === true ? "saved" : "failed");
    } catch {
      setStatus("failed");
    }
  }

  return (
    <form className="release" action="/api/release-notice" method="post" onSubmit={onSubmit}>
      <label htmlFor={fieldId}>Get early access</label>
      <div className="release-row">
        <input
          id={fieldId}
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          placeholder="you@company.com"
          disabled={status === "saving"}
        />
        <button className="btn-primary" type="submit" disabled={status === "saving"}>
          Join the list
        </button>
      </div>
      <p className="release-status" role="status">
        {status === "saved" ? "Saved. We'll email this address when we release." : null}
        {status === "failed" ? "That address was not saved. Try again." : null}
      </p>
    </form>
  );
}
