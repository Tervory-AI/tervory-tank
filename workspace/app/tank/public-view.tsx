"use client";

import { useState } from "react";

const ROSTER = [
  { id: "m1", name: "base-intake", role: "Base", state: "warm", calls: 142 },
  { id: "m2", name: "tiger-watch", role: "Tiger", state: "warm", calls: 88 },
  { id: "m3", name: "radix-gate", role: "Radix", state: "idle", calls: 21 },
  { id: "m4", name: "zenas-moot", role: "Zenas", state: "warm", calls: 56 },
];

const TASKS = [
  { id: "q1", title: "Refresh Capstone batch", worker: "base-intake", status: "done", ago: "4 min" },
  { id: "q2", title: "Digest Tiger watches", worker: "tiger-watch", status: "running", ago: "now" },
  { id: "q3", title: "Radix release brief", worker: "radix-gate", status: "queued", ago: "—" },
  { id: "q4", title: "Publish Moot fixture", worker: "zenas-moot", status: "done", ago: "22 min" },
];

export function TankPublic() {
  const [tab, setTab] = useState<"roster" | "queue">("roster");
  const [open, setOpen] = useState(ROSTER[0].id);
  const active = ROSTER.find((r) => r.id === open) ?? ROSTER[0];

  return (
    <main className="tk-public" aria-label="Tank">
      <header>
        <p className="tk-eyebrow">Tank</p>
        <h1>Roster and queue</h1>
        <p className="tk-lede">Who is warm, what is on the queue, and the receipts when a task lands.</p>
      </header>
      <div className="tk-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "roster"} onClick={() => setTab("roster")}>Roster</button>
        <button type="button" role="tab" aria-selected={tab === "queue"} onClick={() => setTab("queue")}>Queue</button>
      </div>
      {tab === "roster" ? (
        <div className="tk-split">
          <ul>
            {ROSTER.map((r) => (
              <li key={r.id}>
                <button type="button" className={open === r.id ? "on" : undefined} onClick={() => setOpen(r.id)}>
                  <strong>{r.name}</strong>
                  <span>{r.role} · {r.state} · {r.calls} calls</span>
                </button>
              </li>
            ))}
          </ul>
          <article>
            <h2>{active.name}</h2>
            <p>{active.role}</p>
            <dl>
              <div><dt>State</dt><dd>{active.state}</dd></div>
              <div><dt>Calls (30d)</dt><dd>{active.calls}</dd></div>
            </dl>
          </article>
        </div>
      ) : (
        <ul className="tk-queue">
          {TASKS.map((t) => (
            <li key={t.id}>
              <span data-st={t.status}>{t.status}</span>
              <strong>{t.title}</strong>
              <em>{t.worker} · {t.ago}</em>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
