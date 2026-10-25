"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function TankPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Tank">
      <h1 className="pp-title">Tank</h1>
      <p className="pp-lede">Tank runs the roster and the queue. Ask it about a worker, or open a past task receipt.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Tank about a worker, or open a past task…"
          aria-label="Ask Tank"
        />
        <button type="button">Open queue</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Worker</th>
              <th>Status</th>
              <th>Calls</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">Queue is empty. Tasks and roster rows appear here when Tank reports them — this page does not invent workers or volumes.</p>
      </div>
      <p className="pp-learned">What Tank has learned for you — nothing saved yet. Queue patterns show after real tasks land.</p>
      <p className="pp-foot">Tank · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
