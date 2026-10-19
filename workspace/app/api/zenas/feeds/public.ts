/** What may cross from the other region's box: names, counts, dates, errors. */

export type PublicSource = {
  id: string;
  title: string;
  region: string;
  documents: number;
  last_load: string | null;
  errors: string[];
};

export type PublicScore = {
  region: string;
  kind: string;
  area: string;
  jurisdiction: string;
  cases: number;
  outcome_agreement: number;
  element_agreement: number;
  citations_valid: number;
  cost_per_case: number;
  set: string;
  scored_by: string;
  label: string;
};

function rowsFrom(payload: unknown, key: string): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object" && Array.isArray((payload as Record<string, unknown>)[key])) {
    return (payload as Record<string, unknown>)[key] as unknown[];
  }
  return [];
}

function cleanError(value: unknown): string {
  const text = String(value ?? "").replace(/sk-[A-Za-z0-9_-]{8,}/g, "").trim();
  if (!text || /api[_-]?key|token|secret|password/i.test(text)) return "";
  return text.slice(0, 240);
}

export function publicFeeds(payload: unknown): { region: string; sources: PublicSource[] } {
  const root = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  const region = String(root.region ?? "");
  const sources = rowsFrom(payload, "sources").flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const errors: string[] = [];
    if (Array.isArray(row.errors)) {
      for (const entry of row.errors) {
        const clean = cleanError(entry);
        if (clean) errors.push(clean);
      }
    } else if (row.last_status === "error") {
      const clean = cleanError(row.detail);
      if (clean) errors.push(clean);
    }
    const last = row.last_load ?? row.last_update;
    return [{
      id: String(row.source_id ?? row.id ?? ""),
      title: String(row.name ?? row.title ?? row.source_id ?? ""),
      region: String(row.region ?? region),
      documents: Number(row.documents ?? row.document_count ?? 0),
      last_load: typeof last === "string" ? last : null,
      errors,
    }];
  });
  return { region, sources };
}

export function publicScores(payload: unknown): { region: string; runs: PublicScore[] } {
  const root = payload && typeof payload === "object" ? (payload as Record<string, unknown>) : {};
  const region = String(root.region ?? "");
  const runs = rowsFrom(payload, "runs").flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const kind = String(row.kind ?? "");
    const codeBaseline = kind === "legalbench";
    return [{
      region: String(row.region ?? region),
      kind,
      area: String(row.area ?? ""),
      jurisdiction: String(row.jurisdiction ?? ""),
      cases: Number(row.cases ?? 0),
      outcome_agreement: Number(row.outcome_agreement ?? 0),
      element_agreement: Number(row.element_agreement ?? 0),
      citations_valid: Number(row.citations_valid ?? 0),
      cost_per_case: Number(row.cost_per_case ?? 0),
      set: String(row.set ?? ""),
      scored_by: codeBaseline ? "code baseline" : "",
      label: codeBaseline ? "LegalBench code baseline" : "",
    }];
  });
  return { region, runs };
}

export function loadBody(source: string, region: "us-east" | "za"): { source: string; home_region: "us-east" | "za" } {
  return { source, home_region: region };
}
