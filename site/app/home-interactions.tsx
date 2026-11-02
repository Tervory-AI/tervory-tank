"use client";

import { useEffect, useId, useState } from "react";
import { homeCopy as copy } from "./home-copy";

export const engineStages = [
  { title: "Cheapest Frontier Model", meta: "Auto-checked", summary: "Cheapest available model picked", body: copy["112:2552"], example: "e.g. DeepSeek $2/1M picked over Anthropic $15/1M" },
  { title: "Shadow Run", meta: "Runs alongside", summary: "Proves a lighter, cheaper model", body: copy["112:2557"], example: "e.g. lighter model $0.80/1M vs frontier $2/1M, same answer" },
  { title: "Cached Answers & Internal Code", meta: "Repeat or similar prompts", summary: "Then internal code at $0", body: copy["112:2562"], example: "e.g. a repeat prompt answered from cache at $0" },
  { title: "Savings Grow as It Learns", meta: "Grows with your usage", summary: "Learns your business", body: copy["112:2571"], example: "e.g. $40 saved in month 1 → $1,280 in month 8" },
  { title: "Bulk / Batch Rates", meta: "Scheduled work", summary: "Large loads and non-urgent work", body: copy["203:2251"], example: "e.g. $2.00/1M → $1.00/1M, back within 24 hours" },
];

function EngineVisual({ stage }: { stage: number }) {
  if (stage === 0) return <div className="engine-visual"><small>Prices checked every 4 hours · e.g. $/1M</small><div className="price-chips">{["Anthropic $15", "✓ DeepSeek $2", "OpenAI $10", "Kimi $3"].map((v, i) => <span className={i === 1 ? "chosen" : ""} key={v}>{v}</span>)}</div></div>;
  if (stage === 1) return <div className="engine-visual shadow-lines"><span>Frontier model <i /></span><span>Lighter model <i /></span><small>✓ Same quality of answers</small></div>;
  if (stage === 2) return <div className="engine-visual cache-path"><span>Repeat / similar</span> → <span>Cache</span> → <span>Internal code · $0</span></div>;
  if (stage === 3) return <div className="engine-visual"><small>e.g. $40 → $1,280 saved a month</small><div className="growth-bars" aria-hidden="true">{[6, 8, 12, 15, 21, 30, 45, 64].map((height, i) => <i key={i} style={{ height }} />)}</div></div>;
  return <div className="engine-visual batch-visual"><strong>−50%</strong><div><small>before the first prompt is sent</small><small>24-hour turnaround</small><i /></div></div>;
}

export function EngineDiagram() {
  const [stage, setStage] = useState(0);
  const [manual, setManual] = useState(false);
  const prefix = useId();
  useEffect(() => {
    if (manual || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setStage((s) => (s + 1) % engineStages.length), 6500);
    return () => window.clearInterval(timer);
  }, [manual]);
  function select(index: number) { setManual(true); setStage(index); }
  return <div className="engine-interactive" onFocusCapture={() => setManual(true)} onMouseEnter={() => setManual(true)}>
    <div className="engine-options" role="tablist" aria-label="Tank stages">{engineStages.map((item, i) => <button key={item.title} id={`${prefix}-tab-${i}`} role="tab" aria-selected={i === stage} aria-controls={`${prefix}-panel`} tabIndex={i === stage ? 0 : -1} onClick={() => select(i)} onKeyDown={(e) => { if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? 0 : e.key === "End" ? 4 : (stage + (e.key === "ArrowRight" ? 1 : 4)) % 5; select(next); document.getElementById(`${prefix}-tab-${next}`)?.focus(); } }}>{i + 1} · {item.title}</button>)}</div>
    <div className="engine-layout"><div className="engine-rail">{engineStages.map((item, i) => <button key={item.title} className={`engine-node ${stage === i ? "active" : ""}`} onClick={() => select(i)} aria-pressed={stage === i}><span className="stage-number">{i + 1}</span><span className="engine-node-copy"><strong>{item.title}</strong><small>{item.meta}</small><span>{item.summary}</span></span><EngineVisual stage={i} /></button>)}</div>
      <div className="engine-inspector" role="tabpanel" id={`${prefix}-panel`} aria-labelledby={`${prefix}-tab-${stage}`}><p className="eyebrow">{stage + 1} · {engineStages[stage].title}</p><h3>{engineStages[stage].title}</h3><p>{engineStages[stage].body}</p><div className="inspector-example"><small>Example</small><p>{engineStages[stage].example}</p></div></div>
    </div>
  </div>;
}

const rigCaptions = ["Your product, as listed", "Rig is pairing the accessories that fit", "Rig is searching the market for the best prices", "Rig makes sure your site beats or matches them", "Quote ready · everything that fits, at a price that beats or matches the market"];
const rigActions = ["Pair accessories", "Search the market", "Beat or match", "Get A Quote", "Accept & pay"];
const options = ["Cross-store fulfilment", "Live availability", "Payment capture on Accept", "Auto-order", "Blind shipping"];

export function RigShowcase() {
  const [stage, setStage] = useState(0);
  const [manual, setManual] = useState(false);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (manual || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setStage((s) => s === 4 ? 0 : s + 1), 5500);
    return () => window.clearInterval(timer);
  }, [manual]);
  return <section className="rig-showcase" id="rig" onFocusCapture={() => setManual(true)} onMouseEnter={() => setManual(true)}>
    <div className="rig-copy"><p className="eyebrow">02 · Rig</p><img src="/home/67-610-imgArtwork.svg" width="86.52" height="48" alt="Rig" loading="lazy" /><h3>{copy["127:2857"]}</h3><p className="eyebrow option-heading">Optional · your store switches these on</p><div className="rig-switches">{options.map(label => <button key={label} role="switch" aria-checked={!!enabled[label]} onClick={() => setEnabled((old) => ({ ...old, [label]: !old[label] }))}><span className="switch-track"><i /></span><span>{label}</span><small>{enabled[label] ? "On" : "Off"}</small><span className="tag optional">Optional</span></button>)}</div><p className="rig-note">Off by default. Each one runs only when your store switches it on.</p></div>
    <div className="rig-diagram"><img className="rig-glow" src="/home/67-610-imgGlow.svg" alt="" width="1220" height="1060" loading="lazy" /><p className="rig-caption"><img src="/home/67-610-imgCaptionDot.svg" width="8" height="8" alt="" />{rigCaptions[stage]}</p><div className="rig-product-row"><div className="rig-product"><strong>Product</strong><small>Your listing</small></div><div className={`rig-accessories ${stage > 0 ? "revealed" : ""}`} aria-hidden={stage === 0}>{["A", "B", "C"].map((letter, i) => <div key={letter}><span>Accessory {letter}<small>e.g. ${[19, 24, 14][i]}</small></span><small className="fits">✓ Fits</small></div>)}</div><div className="rig-price"><small>Your price · e.g.</small><strong>${stage >= 3 ? "94" : "104"}</strong><p>{stage >= 3 ? "Beats the best market price by e.g. $1" : stage === 2 ? "e.g. $9 above the best market price" : stage === 1 ? "Listed price · 3 accessories that fit, paired" : "Listed price"}</p></div></div>
      <div className={`rig-market ${stage >= 2 ? "revealed" : ""}`}><p>Market prices · example</p><div className="market-rail">{[99, 95, 112].map((price, i) => <div key={price} className={`seller seller-${i}`}><img src="/home/67-610-imgSellerA.svg" width="10" height="10" alt="" /><small>Seller {String.fromCharCode(65 + i)} e.g. ${price}</small></div>)}<div className={`your-price ${stage >= 3 ? "matched" : ""}`}><i /><small>Your price e.g. ${stage >= 3 ? "94" : "104"}</small></div><span className="best-market">Best market e.g. $95</span></div></div>
      <div className="rig-controls"><p>{stage === 4 ? "Quote: Product + 3 accessories that fit · e.g. $151" : "\u00a0"}</p>{<button className="home-button" onClick={() => { setManual(true); setStage(s => s === 4 ? 0 : s + 1); }}>{rigActions[stage]}</button>}</div>
    </div>
  </section>;
}

const columns = ["ledger_id", "model", "tokens_in", "tokens_out", "cost_usd", "baseline_cost_usd", "discount_usd", "latency_ms", "batch"];
const rows = [["led_7f3a91", "luna", "12,400", "1,850", "0.0022", "0.2165", "0.2143", "820", "no"], ["led_7f3a92", "skala", "3,200", "600", "0.0000", "0.0620", "0.0620", "12", "no"], ["led_7f3a93", "astra", "8,000", "2,400", "0.2000", "0.2000", "0.0000", "2,140", "no"], ["led_7f3a94", "luna", "40,000", "6,000", "0.0035", "0.7000", "0.6965", "—", "yes"]];

export function ReceiptExample() {
  const [view, setView] = useState(0);
  const prefix = useId();
  function exportCsv() {
    const data = view ? [columns, ...rows] : [["metric", "value"], ["Saved to date", "1284.50"], ["Saved this month", "312.40"], ["Spent", "176.10"], ["Would have cost", "488.50"], ["Done at no AI cost", "1942"], ["Ana", "142.10"], ["Sam", "98.30"], ["You", "72.00"]];
    const csv = data.map(row => row.map(value => `"${value.replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = view ? "tervory-per-call-example.csv" : "tervory-savings-example.csv"; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="receipt-example"><div className="receipt-tabs" role="tablist" aria-label="Receipt view">{["What you saved", "Per-call receipt"].map((label, i) => <button role="tab" id={`${prefix}-tab-${i}`} aria-controls={`${prefix}-panel`} aria-selected={view === i} tabIndex={view === i ? 0 : -1} key={label} onClick={() => setView(i)} onKeyDown={(e) => { if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? 0 : e.key === "End" ? 1 : 1 - view; setView(next); document.getElementById(`${prefix}-tab-${next}`)?.focus(); } }}>{label}</button>)}<span className="tag example">Example</span></div>
    <div role="tabpanel" id={`${prefix}-panel`} aria-labelledby={`${prefix}-tab-${view}`} className="receipt-panel">{view === 0 ? <><p className="receipt-caption">Your savings <small>Updated 14:32:08 UTC</small></p><div className="saved-total"><small>Saved to date</small><strong>$1,284.50</strong><p>vs the standard model</p></div><div className="receipt-stats">{[["Saved this month", "$312.40", "64% less than it would have cost (2.8× cheaper)"], ["Spent and would have cost", "$176.10", "would have cost $488.50"], ["Done at no AI cost", "1,942", "steps done by our own tools or reused answers"]].map(([label, value, note]) => <div key={label}><small>{label}</small><strong>{value}</strong><p>{note}</p></div>)}</div><div className="receipt-charts"><div><small>Saved per day · last 14 days</small><div className="daily-bars" aria-label="Illustrated daily savings">{[40, 36, 44, 42, 48, 46, 52, 49, 56, 54, 60, 58, 65, 70].map((height, i) => <i key={i} style={{ height }} />)}</div></div><div><small>Saved by team member</small>{[["Ana", "$142.10"], ["Sam", "$98.30"], ["You", "$72.00"]].map(([name, value]) => <p className="member" key={name}><span>{name}</span><span>{value}</span></p>)}</div></div></> : <><p className="receipt-caption">Per-call receipt <small>Every call, itemized · all values e.g.</small></p><div className="receipt-table-scroll" tabIndex={0}><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row[0]}>{row.map((cell, i) => <td key={i}>{cell}</td>)}</tr>)}</tbody></table></div><div className="receipt-summary"><p>4 calls · cost $0.2057 · standard $1.1785</p><strong>saved $0.9728</strong></div></>}</div>
    <div className="receipt-exports"><button onClick={exportCsv}>Export CSV</button><button onClick={() => window.print()}>Export PDF</button><small>Prices e.g. astra $10/$50 vs luna $0.10/$0.50 per 1M tokens</small></div>
  </div>;
}
