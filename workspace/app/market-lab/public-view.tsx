"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function MarketLabPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Market Lab">
      <h1 className="pp-title">Market Lab</h1>
      <p className="pp-lede">Market Lab turns sourced feeds into readings. Ask it for a shelf brief, or open a past reading.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Market Lab for a reading, or open a past brief…"
          aria-label="Ask Market Lab"
        />
        <button type="button">Add feed</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Reading</th>
              <th>Delta</th>
              <th>Source</th>
              <th>Status</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No readings yet. Sourced Market Lab signals appear here when feeds have rows — this page does not invent percentages.</p>
      </div>
      <p className="pp-learned">What Market Lab has learned for you — nothing saved yet. Feed patterns show after real readings land.</p>
      <p className="pp-foot">Market Lab · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
