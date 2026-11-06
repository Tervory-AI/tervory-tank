"use client";
import { useEffect, useState } from "react";
import { radixJSON } from "./io";

type Figure = { id: string; status: string; value: unknown; unknown_cost_calls?: number };
export type Summary = { scans: number | null; findings: { id: string; value: number }[] | null; receipts: number | null; spend: number | null };
const severities = ["critical", "high", "medium", "low", "info", "unknown"];
const unknown: Summary = { scans: null, findings: null, receipts: null, spend: null };
const count = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
export const FIRST_SCAN = "Upload your code in Chats, then confirm radix.repo.scan.";

export function summary(value: unknown): Summary {
  if (!value || typeof value !== "object") return unknown;
  const data = value as { product?: unknown; figures?: unknown; tank?: unknown };
  if (data.product !== "radix" || !Array.isArray(data.figures) || !Array.isArray(data.tank)) return unknown;
  const figures = [...data.figures, ...data.tank].filter((item): item is Figure => !!item && typeof item === "object");
  const find = (id: string) => figures.find((item) => item.id === id && item.status === "available");
  const scans = find("radix.scans")?.value;
  const findings = find("radix.findings_by_severity")?.value;
  const executions = find("tank.work_by_execution")?.value;
  const spend = find("tank.spend");
  const validRows = (rows: unknown, ids: string[]): rows is { id: string; value: number }[] =>
    Array.isArray(rows) && rows.length === ids.length && new Set(rows.map((row) => row?.id)).size === ids.length &&
    rows.every((row) => row && ids.includes(row.id) && count(row.value));
  return {
    scans: count(scans) ? scans : null,
    findings: validRows(findings, severities) ? findings : null,
    receipts: validRows(executions, ["code", "cache", "model"]) ? executions.reduce((total, row) => total + row.value, 0) : null,
    spend: typeof spend?.value === "number" && Number.isFinite(spend.value) && spend.value >= 0 && !spend.unknown_cost_calls ? spend.value : null,
  };
}

export function SeverityChart({ rows }: { rows: Summary["findings"] }) {
  const filled = rows?.some((row) => row.value > 0);
  const maximum = Math.max(1, ...(rows ?? []).map((row) => row.value));
  return <svg role="img" aria-label="Findings by severity" viewBox="0 0 360 170" style={{ width: "100%", height: "auto" }}>
    {[20, 45, 70, 95, 120].map((y) => <line key={y} x1="30" x2="350" y1={y} y2={y} stroke="#B8BFD0" />)}
    <path d="M30 20V145H350" fill="none" stroke="#001840" />
    <text x="12" y="148" fill="#001840">0</text>
    {filled ? rows!.map((row, index) => <g key={row.id}>
      <rect x={40 + index * 51} y={145 - row.value / maximum * 115} width="28" height={row.value / maximum * 115} fill="#A16207"><title>{`${row.id}: ${row.value}`}</title></rect>
      <text x={40 + index * 51} y="164" fontSize="9" fill="#001840">{row.id}</text>
    </g>) : null}
  </svg>;
}

export function SummaryView({ data, section }: { data: Summary; section: string }) {
  const findings = data.findings?.reduce((total, row) => total + row.value, 0) ?? null;
  return <section aria-label="Radix results">
    <div className="rx-checks">
      <article className="rx-card"><h2>Scans</h2><p>{data.scans ?? "—"}</p><p>{FIRST_SCAN}</p></article>
      <article className="rx-card"><h2>Findings by severity</h2><p>{findings ?? "—"}</p><SeverityChart rows={data.findings} /><p>{FIRST_SCAN}</p></article>
      <article className="rx-card"><h2>Receipts</h2><p>{data.receipts ?? "—"}</p><p>{data.spend === null ? "—" : "$" + data.spend.toFixed(2)}</p><p>{FIRST_SCAN}</p></article>
    </div>
    {section !== "Overview" ? <div className="rx-card rx-empty">
      <h2>{section === "Findings" && findings === 0 ? "No findings yet" : section === "Reports" && data.scans === 0 ? "No reports yet" : section}</h2>
      <p>{FIRST_SCAN}</p><a href="/chats" className="rx-text-button">Chats</a>
    </div> : null}
  </section>;
}

export function RadixSummary({ section }: { section: string }) {
  const [data, setData] = useState<Summary>(unknown);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const refresh = () => setRevision(value => value + 1);
    window.addEventListener("radix:refresh", refresh);
    return () => window.removeEventListener("radix:refresh", refresh);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void radixJSON("/api/case-studies/radix", { signal: controller.signal }).then(summary)
      .then((next) => { if (!controller.signal.aborted) setData(next); })
      .catch(() => { if (!controller.signal.aborted) setData(unknown); });
    return () => controller.abort();
  }, [revision]);
  return <SummaryView data={data} section={section} />;
}
