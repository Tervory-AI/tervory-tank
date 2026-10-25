"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function BaseDocument() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Base">
      <h1 className="pp-title">Base</h1>
      <p className="pp-lede">Base finds and verifies people and businesses from public records. Ask it to work a list, or open a past job.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Base to verify a list, or open a past job…"
          aria-label="Ask Base"
        />
        <button type="button">Upload list</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>List</th>
              <th>Records</th>
              <th>Verified</th>
              <th>Cost</th>
              <th>Would have cost</th>
              <th>Saved</th>
              <th>Status</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No jobs yet. When Base finishes a list for this account, the rows appear here — this page does not invent record counts or costs.</p>
      </div>
      <p className="pp-learned">What Base has learned for you — nothing saved yet. Patterns show here after real jobs complete.</p>
      <p className="pp-foot">Base · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
