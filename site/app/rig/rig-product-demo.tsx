"use client";

import { useState } from "react";
import { rigCopy as copy } from "./rig-copy";

const stages = [["56:178", "56:180"], ["56:187", "56:189"], ["56:198", "56:200"], ["56:207", "56:209"], ["56:216", "56:218"], ["56:225", "56:227"], ["56:234", "56:236"]];

export function RigProductDemo() {
  const [stage, setStage] = useState(0);
  return <section id="how" className="rp-how" aria-labelledby="how-title">
    <div className="rp-how-head"><h2 id="how-title">{copy["56:171"]}</h2></div>
    <div className="rp-stages" aria-label="Rig stages">{stages.map(([title], index) => <div className="rp-step" key={title}><button type="button" aria-pressed={stage === index} onClick={() => setStage(index)}>{copy[title]}</button></div>)}</div>
    <div className="rp-demo-panels"><section className="rp-panel"><h3>{copy[stages[stage][0]]}</h3><p>No store data yet. Connect your store in Rig to fill these results.</p></section>
      <section className="rp-panel"><h3>Receipt</h3><dl><dt>Orders</dt><dd>0</dd><dt>Cost</dt><dd>—</dd><dt>Saved</dt><dd>—</dd></dl><p>Start a store search in Rig to fill this receipt.</p></section></div>
  </section>;
}
