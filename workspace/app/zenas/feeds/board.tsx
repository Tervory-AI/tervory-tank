"use client";

import { useState } from "react";
import type { PublicScore, PublicSource } from "@/app/api/zenas/feeds/public";

type Region = "us-east" | "za";

export function FeedSwitch({
  initialRegion,
  initialSources,
  initialScores,
  initialReview,
  note,
}: {
  initialRegion: Region;
  initialSources: PublicSource[];
  initialScores: PublicScore[];
  initialReview: "on" | "off";
  note: string;
}) {
  const [region, setRegion] = useState<Region>(initialRegion);
  const [sources, setSources] = useState(initialSources);
  const [scores, setScores] = useState(initialScores);
  const [review, setReview] = useState<"on" | "off">(initialReview);
  const [message, setMessage] = useState(note);
  const [busy, setBusy] = useState("");

  async function choose(next: Region) {
    setRegion(next);
    setMessage("");
    const [feeds, scored, switched] = await Promise.all([
      fetch(`/api/zenas/feeds/region?region=${next}`),
      fetch(`/api/zenas/selftest?region=${next}`),
      fetch(`/api/zenas/review-switch?region=${next}`),
    ]);
    if (!feeds.ok) {
      setSources([]);
      setMessage("Feeds could not be loaded.");
    } else {
      const body = (await feeds.json()) as { sources?: PublicSource[]; note?: string };
      setSources(body.sources ?? []);
      setMessage(body.note ?? "");
    }
    if (scored.ok) {
      const body = (await scored.json()) as { runs?: PublicScore[] };
      setScores(body.runs ?? []);
    } else {
      setScores([]);
    }
    if (switched.ok) {
      const body = (await switched.json()) as { review?: string };
      setReview(body.review === "on" ? "on" : "off");
    }
  }

  async function flipReview() {
    const next = review === "on" ? "off" : "on";
    setBusy("review");
    const res = await fetch("/api/zenas/review-switch", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ region, review: next }),
    });
    setBusy("");
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setMessage(body?.error || "The switch did not change.");
      return;
    }
    setReview(next);
  }

  async function load(source: string) {
    setBusy(source);
    setMessage("");
    const res = await fetch("/api/zenas/feeds/region/load", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ source, region }),
    });
    setBusy("");
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setMessage(body?.error || "The load did not start.");
      return;
    }
    setMessage(`${source} started.`);
    await choose(region);
  }

  return (
    <>
      <div className="switch" role="group" aria-label="Region">
        <button type="button" className={region === "us-east" ? "on" : ""} onClick={() => choose("us-east")}>
          US
        </button>
        <button type="button" className={region === "za" ? "on" : ""} onClick={() => choose("za")}>
          South Africa
        </button>
      </div>
      {message ? <p className="note">{message}</p> : null}
      <p className="note">
        Lawyer review is {review}.{" "}
        <button type="button" disabled={busy === "review"} onClick={flipReview}>
          {review === "on" ? "Turn lawyer review off" : "Turn lawyer review on"}
        </button>
      </p>
      <h2>Test scores</h2>
      <p className="note">LegalBench rows are a code baseline, not a model score.</p>
      {scores.length === 0 ? <p>No scores yet.</p> : (
        <table>
          <thead>
            <tr>
              <th>Area</th>
              <th>Kind</th>
              <th>Cases</th>
              <th>Outcome</th>
              <th>Elements</th>
              <th>Citations</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {scores.map((row) => (
              <tr key={`${row.kind}-${row.area}-${row.set}`}>
                <td>{row.area || row.jurisdiction}</td>
                <td>{row.label || row.set || row.kind}</td>
                <td className="meta">{row.cases}</td>
                <td className="meta">{row.outcome_agreement}%</td>
                <td className="meta">{row.element_agreement}%</td>
                <td className="meta">{row.citations_valid}%</td>
                <td className="meta">{row.cost_per_case}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h2>Sources</h2>
      <table>
        <thead>
          <tr>
            <th>Source</th>
            <th>Documents</th>
            <th>Last load</th>
            <th>Errors</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sources.map((row) => (
            <tr key={row.id}>
              <td>{row.title}</td>
              <td className="meta">{row.documents}</td>
              <td className="meta">{row.last_load ?? "—"}</td>
              <td>{row.errors.join(" ")}</td>
              <td>
                <button type="button" disabled={busy === row.id} onClick={() => load(row.id)}>
                  {busy === row.id ? "Starting" : "Load now"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
