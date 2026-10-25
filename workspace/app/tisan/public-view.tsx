"use client";

import { useState } from "react";

const THREADS = [
  {
    id: "t1",
    title: "Counter brief — Saturday rush",
    preview: "Two checkers on Form 4473; keep the safe key with the closer.",
    messages: [
      { who: "You", text: "Draft the Saturday counter brief for Kapaa." },
      { who: "Tisan", text: "Two checkers on every 4473. Safe key stays with the closer. Reman 9mm on the endcap only after noon." },
      { who: "You", text: "Add the TLR watch note from Tiger." },
      { who: "Tisan", text: "Added: TLR-1 HL is under ceiling — mention it if a customer asks for a light package." },
    ],
  },
  {
    id: "t2",
    title: "Gold note — transfer desk",
    preview: "Keep outbound Form 3 language tight; no improvising on ATF timing.",
    messages: [
      { who: "You", text: "Pin the gold note for Form 3 outbound." },
      { who: "Tisan", text: "Pinned. Outbound Form 3 uses the standard letter only. Timing questions go to the responsible person." },
    ],
  },
  {
    id: "t3",
    title: "Intake chat — Capstone list",
    preview: "Friday intake cleared 18 rows; three need a second website pass.",
    messages: [
      { who: "Tisan", text: "Friday intake: 18 rows cleared, 3 need a second website pass before Base files them." },
    ],
  },
];

export function TisanPublic() {
  const [open, setOpen] = useState(THREADS[0].id);
  const active = THREADS.find((t) => t.id === open) ?? THREADS[0];
  return (
    <main className="ti-public" aria-label="Tisan">
      <header>
        <p className="ti-eyebrow">Tisan</p>
        <h1>Briefs and chats</h1>
        <p className="ti-lede">Keep the working brief next to the conversation. Open a thread and read the thread end-to-end.</p>
      </header>
      <div className="ti-split">
        <ul>
          {THREADS.map((t) => (
            <li key={t.id}>
              <button type="button" className={open === t.id ? "on" : undefined} onClick={() => setOpen(t.id)}>
                <strong>{t.title}</strong>
                <span>{t.preview}</span>
              </button>
            </li>
          ))}
        </ul>
        <article>
          <h2>{active.title}</h2>
          <ol>
            {active.messages.map((m, i) => (
              <li key={i} data-who={m.who}>
                <span>{m.who}</span>
                <p>{m.text}</p>
              </li>
            ))}
          </ol>
        </article>
      </div>
    </main>
  );
}
