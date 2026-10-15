"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FeedbackButtons } from "./feedback-buttons";

type Msg = {
  role: "user" | "assistant";
  content: string;
  meta?: { ledger_id: string; model: string; rung: number; cost_usd: number; latency_ms: number };
};

export default function ChatPage() {
  const router = useRouter();
  const [gate, setGate] = useState<"check" | "show">("check");
  const [thread, setThread] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetch("/onboarding/status", { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) return { needs: false };
        return (await res.json()) as { needs?: boolean };
      })
      .then((data) => {
        if (!live) return;
        if (data.needs) router.replace("/onboarding");
        else setGate("show");
      })
      .catch(() => {
        if (live) setGate("show");
      });
    return () => {
      live = false;
    };
  }, [router]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    const next: Msg[] = [...thread, { role: "user", content: text }];
    setThread(next);
    setDraft("");
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })) }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setThread([
        ...next,
        {
          role: "assistant",
          content: data.content,
          meta: { ledger_id: data.ledger_id, model: data.model, rung: data.rung, cost_usd: data.cost_usd, latency_ms: data.latency_ms },
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  if (gate !== "show") return <p className="meta">Loading…</p>;

  return (
    <>
      <div className="thread">
        {thread.length === 0 && (
          <p style={{ color: "var(--muted)" }}>
            Ask for anything a business owner would ask. Every answer shows which model answered and what it cost.
          </p>
        )}
        {thread.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.content}
            {m.meta && (
              <div className="meta">
                {m.meta.model} · rung {m.meta.rung} · ${m.meta.cost_usd.toFixed(5)} · {m.meta.latency_ms} ms
                {" · "}
                <FeedbackButtons ledgerId={m.meta.ledger_id} />
              </div>
            )}
          </div>
        ))}
        {error && <p className="err">{error}</p>}
      </div>
      <div className="composer">
        <form onSubmit={send}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                (e.currentTarget.form as HTMLFormElement | null)?.requestSubmit();
              }
            }}
            placeholder="Type a request…"
            disabled={busy}
          />
          <button type="submit" disabled={busy || !draft.trim()}>
            {busy ? "Working…" : "Send"}
          </button>
        </form>
      </div>
    </>
  );
}
