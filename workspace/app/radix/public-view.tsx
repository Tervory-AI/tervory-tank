"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function RadixPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Radix">
      <h1 className="pp-title">Radix</h1>
      <p className="pp-lede">Radix reviews code and releases. Ask it to scan a tree, or open a past findings job.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Radix to scan a tree, or open a past job…"
          aria-label="Ask Radix"
        />
        <button type="button">Upload tree</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Scan</th>
              <th>High</th>
              <th>Medium</th>
              <th>Low</th>
              <th>Status</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No scans yet. Findings appear here after Radix completes a real run — this page does not invent severities or files.</p>
      </div>
      <p className="pp-learned">What Radix has learned for you — nothing saved yet. Release-gate patterns show after real scans.</p>
      <p className="pp-foot">Radix · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
