"use client";

import { useState } from "react";

/** Public product host Main chrome — Figma C5 agent page (ZnphBOJU6657tohGLD3IzS).
 *  Sidebar is app-shell. Jobs stay empty until Tank has live rows. No invented SKUs/%/findings. */
export function SkalaPublic() {
  const [ask, setAsk] = useState("");
  return (
    <main className="pp" aria-label="Skala">
      <h1 className="pp-title">Skala</h1>
      <p className="pp-lede">Skala holds the skills library. Ask it about a skill, or open a past eval job.</p>
      <form
        className="pp-ask"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <input
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          placeholder="Ask Skala about a skill, or open a past eval…"
          aria-label="Ask Skala"
        />
        <button type="button">Review queue</button>
        <button type="submit" className="primary">Ask</button>
      </form>
      <h2 className="pp-section">Jobs</h2>
      <div className="pp-table-wrap">
        <table className="pp-table">
          <thead>
            <tr>
              <th>Skill</th>
              <th>Agent</th>
              <th>Rung</th>
              <th>Eval</th>
              <th>State</th>
              <th>When</th>
            </tr>
          </thead>
        </table>
        <p className="pp-empty" role="status">No skills listed yet. Approved and candidate skills appear here when the library has them — this page does not invent scores.</p>
      </div>
      <p className="pp-learned">What Skala has learned for you — nothing saved yet. Approval patterns show after real evals.</p>
      <p className="pp-foot">Skala · Tervory · Figma C5 agent page chrome (ZnphBOJU6657tohGLD3IzS)</p>
    </main>
  );
}
