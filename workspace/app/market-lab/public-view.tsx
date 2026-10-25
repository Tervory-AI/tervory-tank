"use client";

import { useState } from "react";

const READINGS = [
  { id: "r1", title: "9mm street vs MAP — West", delta: "+2.4%", note: "Three distributors tightened MAP; street still soft on reman." },
  { id: "r2", title: "Optics lead times", delta: "−6 days", note: "LPVO replenishment improved; red-dot allotments still rationed." },
  { id: "r3", title: "FFL transfer velocity (HI)", delta: "+11%", note: "Weekend counters busier; Form 3 outbound backlog clearing." },
  { id: "r4", title: "Powder & primer basket", delta: "Flat", note: "No new allotment letters this week; watch next Tuesday." },
];

const REPORT = {
  title: "Weekly shelf brief",
  body: "West coast 9mm remains the loudest signal. MAP held at two majors while street inventories cleared reman lots. Optics lead times eased on LPVO; keep the TLR and PMAG watches tight — Tiger already flagged both.",
};

export function MarketLabPublic() {
  const [open, setOpen] = useState(READINGS[0].id);
  const active = READINGS.find((r) => r.id === open) ?? READINGS[0];
  return (
    <main className="ml-public" aria-label="Market Lab">
      <header>
        <p className="ml-eyebrow">Market Lab</p>
        <h1>Market readings</h1>
        <p className="ml-lede">Sourced signals from the feeds you run. Open a reading, keep the weekly brief close.</p>
      </header>
      <div className="ml-grid">
        <ul>
          {READINGS.map((r) => (
            <li key={r.id}>
              <button type="button" className={open === r.id ? "on" : undefined} onClick={() => setOpen(r.id)}>
                <strong>{r.title}</strong>
                <span>{r.delta}</span>
              </button>
            </li>
          ))}
        </ul>
        <article>
          <h2>{active.title}</h2>
          <p className="ml-delta">{active.delta}</p>
          <p>{active.note}</p>
          <hr />
          <h3>{REPORT.title}</h3>
          <p>{REPORT.body}</p>
        </article>
      </div>
    </main>
  );
}
