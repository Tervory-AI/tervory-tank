"use client";

import { useState } from "react";

const SKILLS = [
  { id: "s1", name: "base.intake-clean", agent: "Base", rung: 3, score: 0.92, state: "approved", note: "Cleans Capstone rows and flags missing websites before Base files them." },
  { id: "s2", name: "tiger.watch-digest", agent: "Tiger", rung: 2, score: 0.88, state: "candidate", note: "Daily digest of price and stock moves for the watches on the board." },
  { id: "s3", name: "tisan.brief-pin", agent: "Tisan", rung: 4, score: 0.95, state: "approved", note: "Pins a gold brief and refuses improvised ATF timing language." },
  { id: "s4", name: "radix.release-gate", agent: "Radix", rung: 3, score: 0.81, state: "candidate", note: "Blocks a release brief when High findings remain open." },
];

export function SkalaPublic() {
  const [open, setOpen] = useState(SKILLS[0].id);
  const active = SKILLS.find((s) => s.id === open) ?? SKILLS[0];
  return (
    <main className="sk-public" aria-label="Skala">
      <header>
        <p className="sk-eyebrow">Skala</p>
        <h1>Skills library</h1>
        <p className="sk-lede">Every skill with its rung, last eval, and whether it is cleared to run.</p>
      </header>
      <div className="sk-split">
        <ul>
          {SKILLS.map((s) => (
            <li key={s.id}>
              <button type="button" className={open === s.id ? "on" : undefined} onClick={() => setOpen(s.id)}>
                <strong>{s.name}</strong>
                <span>{s.agent} · rung {s.rung} · {(s.score * 100).toFixed(0)}%</span>
              </button>
            </li>
          ))}
        </ul>
        <article>
          <p className="sk-state">{active.state}</p>
          <h2>{active.name}</h2>
          <p>{active.agent} · rung {active.rung}</p>
          <p className="sk-score">{(active.score * 100).toFixed(0)}% last eval</p>
          <p>{active.note}</p>
        </article>
      </div>
    </main>
  );
}
