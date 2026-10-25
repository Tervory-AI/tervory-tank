"use client";

import { useState } from "react";

const WATCHES = [
  { id: "w1", title: "Hornady 9mm 115gr Critical Defense", store: "MidwayUSA", price: "$28.49", was: "$31.99", change: "−11%", stock: "In stock" },
  { id: "w2", title: "Federal Premium 223 Rem 55gr", store: "Sportsman's", price: "$14.99", was: "$14.99", change: "0%", stock: "Low" },
  { id: "w3", title: "Magpul PMAG 30 Gen M3", store: "Primary Arms", price: "$12.59", was: "$13.95", change: "−10%", stock: "In stock" },
  { id: "w4", title: "Streamlight TLR-1 HL", store: "OpticsPlanet", price: "$139.99", was: "$159.00", change: "−12%", stock: "In stock" },
];

const ALERTS = [
  { id: "a1", title: "Critical Defense back below $29", when: "12 min ago", kind: "Price drop" },
  { id: "a2", title: "Federal 223 low stock at Sportsman's", when: "1 hr ago", kind: "Stock" },
  { id: "a3", title: "TLR-1 HL matched your ceiling", when: "Yesterday", kind: "Price drop" },
];

export function TigerPublic() {
  const [tab, setTab] = useState<"watches" | "alerts">("watches");
  const [open, setOpen] = useState(WATCHES[0].id);

  const active = WATCHES.find((w) => w.id === open) ?? WATCHES[0];

  return (
    <main className="tiger-public" aria-label="Tiger">
      <header>
        <p className="tp-eyebrow">Tiger</p>
        <h1>Price watches</h1>
        <p className="tp-lede">Track shelves you care about. Open a watch, read the move, act when stock or price shifts.</p>
      </header>
      <div className="tp-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "watches"} onClick={() => setTab("watches")}>Watches</button>
        <button type="button" role="tab" aria-selected={tab === "alerts"} onClick={() => setTab("alerts")}>Alerts</button>
      </div>
      {tab === "watches" ? (
        <div className="tp-split">
          <ul className="tp-list">
            {WATCHES.map((w) => (
              <li key={w.id}>
                <button type="button" className={open === w.id ? "on" : undefined} onClick={() => setOpen(w.id)}>
                  <strong>{w.title}</strong>
                  <span>{w.store} · {w.price} <em>{w.change}</em></span>
                </button>
              </li>
            ))}
          </ul>
          <article className="tp-detail">
            <h2>{active.title}</h2>
            <p>{active.store}</p>
            <dl>
              <div><dt>Now</dt><dd>{active.price}</dd></div>
              <div><dt>Was</dt><dd>{active.was}</dd></div>
              <div><dt>Move</dt><dd>{active.change}</dd></div>
              <div><dt>Stock</dt><dd>{active.stock}</dd></div>
            </dl>
          </article>
        </div>
      ) : (
        <ul className="tp-alerts">
          {ALERTS.map((a) => (
            <li key={a.id}>
              <span className="tp-pill">{a.kind}</span>
              <strong>{a.title}</strong>
              <span>{a.when}</span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
