import type { BaseRecord } from "@/lib/tank";

export type ContextReport = {
  records: number;
  creditsPerRecord: number | null;
  unknownCharges: number;
  fields: { field: string; checked: number; baseCorrect: number; contextCorrect: number }[];
};

function comparable(value: unknown): string {
  if (Array.isArray(value)) return JSON.stringify(value.map(comparable).sort());
  if (value && typeof value === "object") {
    return JSON.stringify(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)).map(([key, item]) => [key, comparable(item)]));
  }
  return String(value ?? "").trim().toLowerCase().replace(/\/$/, "");
}

function socialUrls(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(socialUrls);
  if (value && typeof value === "object") return Object.values(value).flatMap(socialUrls);
  if (typeof value !== "string") return [];
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol)) return [];
    return [`${url.hostname.toLowerCase().replace(/^www\./, "")}${url.pathname.replace(/\/$/, "")}`];
  } catch {
    return [];
  }
}

function fieldValue(field: string, value: unknown): string {
  return field === "socials" ? JSON.stringify([...new Set(socialUrls(value))].sort()) : comparable(value);
}

export function contextReport(records: BaseRecord[]): ContextReport {
  const report: ContextReport = { records: 0, creditsPerRecord: null, unknownCharges: 0, fields: [] };
  const fields = new Map<string, ContextReport["fields"][number]>();
  let credits = 0;
  for (const record of records) {
    const trial = record.passes.context_dev;
    if (!trial || !["candidate", "failed", "transport_error", "unknown"].includes(String(trial.status))) continue;
    report.records++;
    if (typeof trial.credits === "number" && Number.isFinite(trial.credits) && trial.credits >= 0) credits += trial.credits;
    else report.unknownCharges++;
    const review = record.passes.context_dev_checked;
    if (review?.checked !== true || !review.expected || typeof review.expected !== "object" || Array.isArray(review.expected)) continue;
    const candidate = trial.fields && typeof trial.fields === "object" ? trial.fields as Record<string, unknown> : {};
    for (const [field, expected] of Object.entries(review.expected)) {
      if (!["name", "website", "description", "socials"].includes(field)) continue;
      const row = fields.get(field) ?? { field, checked: 0, baseCorrect: 0, contextCorrect: 0 };
      row.checked++;
      row.baseCorrect += Number(fieldValue(field, record.profile[field]?.value) === fieldValue(field, expected));
      row.contextCorrect += Number(fieldValue(field, candidate[field]) === fieldValue(field, expected));
      fields.set(field, row);
    }
  }
  report.fields = [...fields.values()];
  report.creditsPerRecord = report.records && !report.unknownCharges ? credits / report.records : null;
  return report;
}
