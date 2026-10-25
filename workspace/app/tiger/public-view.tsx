"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function TigerPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Tiger">
      <h1 className="pp-title">Tiger</h1>
      <p className="pp-lede">Tiger watches shelves you care about. Ask it to track a product, or open a past watch job.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Tiger to watch a product, or open a past job…"
          aria-label="Ask Tiger"
        />
        <button type="button">Add watch</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Watch</th>
              <th>Store</th>
              <th>Price</th>
              <th>Move</th>
              <th>Stock</th>
              <th>Status</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No watches yet. Saved Tiger watches appear here when Tank has them — this page does not invent SKUs or prices.</p>
      </div>
      <p className="pp-learned">What Tiger has learned for you — nothing saved yet. Price and stock patterns show after real watches run.</p>
      <p className="pp-foot">Tiger · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
