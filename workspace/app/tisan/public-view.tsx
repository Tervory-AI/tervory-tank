"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function TisanPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Tisan">
      <h1 className="pp-title">Tisan</h1>
      <p className="pp-lede">Tisan keeps briefs next to the conversation. Ask it to draft a brief, or open a past thread.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Tisan to draft a brief, or open a past thread…"
          aria-label="Ask Tisan"
        />
        <button type="button">New brief</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Brief</th>
              <th>Thread</th>
              <th>Messages</th>
              <th>Status</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No briefs yet. Threads saved in Tisan appear here when Tank has them — this page does not invent messages.</p>
      </div>
      <p className="pp-learned">What Tisan has learned for you — nothing saved yet. Gold notes show after real briefs are pinned.</p>
      <p className="pp-foot">Tisan · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
