"use client";

import { useEffect, useId, useState } from "react";
import { homeCopy as copy } from "./home-copy";

export const engineStages = [
  ["208:2367", "208:2368", "208:2369", "208:2429"],
  ["208:2381", "208:2382", "208:2383", "208:2431"],
  ["208:2391", "208:2392", "208:2393", "208:2433"],
  ["208:2404", "208:2405", "208:2406", "208:2435"],
  ["208:2418", "208:2419", "208:2420", "208:2437"],
].map(([title, meta, summary, number]) => ({ title: copy[title], meta: copy[meta], summary: copy[summary], number: copy[number] }));

function CheckedLabel({ text }: { text: string }) {
  return <span aria-label={text}><i className="diagram-check" aria-hidden="true" />{text.replace(/^✓\s*/, "")}</span>;
}

function EngineVisual({ stage }: { stage: number }) {
  if (stage === 0) return <span className="engine-visual"><small>{copy["208:2371"]}</small><span className="price-chips">{["208:2373", "208:2375", "208:2377", "208:2379"].map((id, i) => <span className={i === 1 ? "chosen" : ""} key={id}>{i === 1 ? <CheckedLabel text={copy[id]} /> : copy[id]}</span>)}</span></span>;
  if (stage === 1) return <span className="engine-visual shadow-lines"><span>{copy["208:2385"]}<i /></span><span>{copy["208:2387"]}<i /></span><small><CheckedLabel text={copy["208:2389"]} /></small></span>;
  if (stage === 2) return <span className="engine-visual cache-path"><span>{copy["208:2396"]}</span><b aria-hidden="true">{copy["208:2397"]}</b><span>{copy["208:2399"]}</span><b aria-hidden="true">{copy["208:2400"]}</b><span>{copy["208:2402"]}</span></span>;
  if (stage === 3) return <span className="engine-visual"><small>{copy["208:2408"]}</small><span className="growth-bars" aria-hidden="true">{[6, 8, 11, 15, 21, 30, 44, 64].map((height, i) => <i key={i} style={{ height }} />)}</span></span>;
  return <span className="engine-visual batch-visual"><strong>{copy["208:2422"]}</strong><span><small>{copy["208:2423"]}</small><small>{copy["208:2424"]}</small><i aria-hidden="true" /></span></span>;
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
    <ol className="engine-rail" aria-label={copy["67:319"]}>{engineStages.map((item, i) => <li key={item.title}>
      <button id={`${prefix}-stage-${i}`} className={`engine-node ${stage === i ? "active" : ""}`} onClick={() => select(i)} aria-pressed={stage === i} onKeyDown={(e) => {
        if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp", "Home", "End"].includes(e.key)) {
          e.preventDefault();
          const next = e.key === "Home" ? 0 : e.key === "End" ? 4 : (i + (["ArrowRight", "ArrowDown"].includes(e.key) ? 1 : 4)) % 5;
          select(next); document.getElementById(`${prefix}-stage-${next}`)?.focus();
        }
      }}><span className="stage-number" aria-hidden="true">{item.number}</span><span className="engine-node-copy"><strong>{item.title}</strong><small>{item.meta}</small><span>{item.summary}</span></span><EngineVisual stage={i} /></button>
    </li>)}</ol>
  </div>;
}

const rigCaptions = [copy["127:2420"], copy["127:2459"], copy["127:2498"], copy["founder:cart-caption"]];
const rigActions = [copy["138:2279"], copy["138:2284"], copy["138:2289"], copy["founder:add-to-cart"]];
const options = ["170:2302", "170:2316", "170:2344", "170:2358"].map(id => copy[id]);
const accessories = [["127:2427", "127:2428"], ["127:2432", "127:2433"], ["127:2437", "127:2438"]];
const sellers = ["127:2446", "127:2448", "127:2450"];

export function RigShowcase() {
  const [stage, setStage] = useState(0);
  const [manual, setManual] = useState(false);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  useEffect(() => {
    if (manual || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setStage((s) => (s + 1) % rigActions.length), 5500);
    return () => window.clearInterval(timer);
  }, [manual]);
  return <section className="rig-showcase" id="rig" onFocusCapture={() => setManual(true)} onMouseEnter={() => setManual(true)}>
    <div className="rig-copy"><p className="eyebrow">{copy["127:2856"]}</p><a className="rig-page-link" href="/rig"><img src="/home/67-610-imgArtwork.svg" width="86.52" height="48" alt="Rig" loading="lazy" /></a><h3>{copy["127:2857"]}</h3><p className="eyebrow option-heading">{copy["127:2859"]}</p><div className="rig-switches">{options.map(label => <button key={label} role="switch" aria-checked={!!enabled[label]} onClick={() => setEnabled((old) => ({ ...old, [label]: !old[label] }))}><span className="switch-track"><i /></span><span className="rig-switch-details"><span>{label}</span><small>{enabled[label] ? copy["170:2311"] : copy["170:2303"]}</small><span className="tag optional">{copy["170:2306"]}</span></span></button>)}</div><p className="rig-note">{copy["127:2901"]}</p></div>
    <div className="rig-diagram" data-stage={stage}><img className="rig-glow" src="/home/67-610-imgGlow.svg" alt="" width="1220" height="1060" loading="lazy" /><p className="rig-caption"><img src="/home/67-610-imgCaptionDot.svg" width="8" height="8" alt="" />{rigCaptions[stage]}</p>
      <div className="rig-product-row">
        <div className="rig-product" data-diagram-shape="product"><strong>{copy["127:2423"]}</strong><small>{copy["127:2424"]}</small></div>
        <div className={`rig-accessories ${stage > 0 ? "revealed" : ""}`} aria-hidden={stage === 0}>{accessories.map(([name, price]) => <div key={name} data-diagram-shape="accessory"><span>{copy[name]}<small>{copy[price]}</small></span><small className="fits"><CheckedLabel text={copy["127:2429"]} /></small></div>)}</div>
        <div className={`rig-price ${stage === 3 ? "matched" : ""}`} data-diagram-shape="price"><small>{copy["127:2440"]}</small><strong>{copy[stage === 3 ? "127:2558" : "127:2441"]}</strong>{stage === 0 && <p>{copy["127:2442"]}</p>}</div>
      </div>
      <div className={`rig-market ${stage >= 2 ? "revealed" : ""}`} data-diagram-shape="market"><p>{copy["127:2443"]}</p><div className="market-rail">{sellers.map((id, i) => <div key={id} className={`seller seller-${i}`}><img src="/home/67-610-imgSellerA.svg" width="10" height="10" alt="" /><small><span className="seller-desktop-label">{copy[id]}</span><span className="seller-mobile-label">{copy[["127:2652", "127:2654", "127:2656"][i]]}</span></small></div>)}<div className={`your-price ${stage === 3 ? "matched" : ""}`}><i /><small>{copy[stage === 3 ? "127:2570" : "127:2453"]}</small></div><span className="best-market">{copy["127:2451"]}</span></div></div>
      <div className="rig-controls"><button className="home-button" data-diagram-shape="cart" onClick={() => { setManual(true); setStage(s => (s + 1) % rigActions.length); }}>{rigActions[stage]}</button></div>
    </div>
  </section>;
}

const columns = ["ledger_id", "model", "tokens_in", "tokens_out", "cost_usd", "baseline_cost_usd", "discount_usd", "latency_ms", "batch"];
const rows: string[][] = [];

export function ReceiptExample() {
  const [view, setView] = useState(0);
  const prefix = useId();
  function exportCsv() {
    const data = view ? [columns, ...rows] : [["metric", "value"], ["Saved to date", "0.00"], ["Saved this month", "0.00"], ["Spent", "0.00"], ["Would have cost", "—"], ["Done at no AI cost", "0"]];
    const csv = data.map(row => row.map(value => `"${value.replaceAll('"', '""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a"); a.href = url; a.download = view ? "tervory-per-call.csv" : "tervory-savings.csv"; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="receipt-example"><div className="receipt-tabs" role="tablist" aria-label="Receipt view">{["What you saved", "Per-call receipt"].map((label, i) => <button role="tab" id={`${prefix}-tab-${i}`} aria-controls={`${prefix}-panel`} aria-selected={view === i} tabIndex={view === i ? 0 : -1} key={label} onClick={() => setView(i)} onKeyDown={(e) => { if (["ArrowRight", "ArrowLeft", "Home", "End"].includes(e.key)) { e.preventDefault(); const next = e.key === "Home" ? 0 : e.key === "End" ? 1 : 1 - view; setView(next); document.getElementById(`${prefix}-tab-${next}`)?.focus(); } }}>{label}</button>)}<span className="tag example">No work yet</span></div>
    <div role="tabpanel" id={`${prefix}-panel`} aria-labelledby={`${prefix}-tab-${view}`} className="receipt-panel">{view === 0 ? <><p className="receipt-caption">Your savings <small>—</small></p><div className="saved-total"><small>Saved to date</small><strong>$0.00</strong><p>vs the standard model</p></div><div className="receipt-stats">{[["Saved this month", "$0.00", "—"], ["Spent and would have cost", "$0.00", "would have cost —"], ["Done at no AI cost", "0", "steps done by our own tools or reused answers"]].map(([label, value, note]) => <div key={label}><small>{label}</small><strong>{value}</strong><p>{note}</p></div>)}</div><div className="receipt-charts"><div><small>Saved per day · last 14 days</small><div className="daily-bars" aria-label="Daily savings: 0">{Array(14).fill(0).map((height, i) => <i key={i} style={{ height }} />)}</div></div><div><small>Saved by team member</small>{[["—", "—"]].map(([name, value]) => <p className="member" key={name}><span>{name}</span><span>{value}</span></p>)}</div></div></> : <><p className="receipt-caption">Per-call receipt <small>No calls yet</small></p><div className="receipt-table-scroll" tabIndex={0}><table><thead><tr>{columns.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>{!rows.length && <tr><td colSpan={columns.length}>No calls yet. Sign in and ask for work to fill this receipt.</td></tr>}{rows.map(row => <tr key={row[0]}>{row.map((cell, i) => <td key={i}>{cell}</td>)}</tr>)}</tbody></table></div><div className="receipt-summary"><p>0 calls · cost $0.00 · standard —</p><strong>saved $0.00</strong></div></>}</div>
    <div className="receipt-exports"><button onClick={exportCsv}>Export CSV</button><button onClick={() => window.print()}>Export PDF</button><small>Sign in and ask for work to fill your savings and receipts.</small></div>
  </div>;
}
