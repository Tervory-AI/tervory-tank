/** Plain shapes for Matters, Review, and the feeds list. No secrets. */

export type ReleasedDocument = {
  id: string;
  kind: string;
  version: number;
  body: string;
  sources: unknown[];
};

export type MatterRow = {
  id: string;
  title: string;
  jurisdiction: string;
  area: string;
  status: string;
  documents: ReleasedDocument[];
};

export type FeedRow = {
  id: string;
  title: string;
  region: string;
  key_name: string;
  key_set: "yes" | "no" | "no key";
  documents: number;
  last_load: string | null;
  errors: string[];
};

export type ReviewMatch = {
  id: string;
  outcome: string;
  jurisdiction: string;
  findings: string[];
};

export type ReviewItem = {
  documentId: string;
  body: string;
  state: string;
  sources: { citation: string; quote: string }[];
  matterId: string;
  title: string;
  jurisdiction: string;
  area: string;
  matches: ReviewMatch[];
};

function rowsFrom(payload: unknown, key: string): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === "object" && Array.isArray((payload as Record<string, unknown>)[key])) {
    return (payload as Record<string, unknown>)[key] as unknown[];
  }
  return [];
}

export function releasedOnly(documents: unknown): ReleasedDocument[] {
  if (!Array.isArray(documents)) return [];
  const out: ReleasedDocument[] = [];
  for (const item of documents) {
    if (!item || typeof item !== "object") continue;
    const doc = item as Record<string, unknown>;
    if (doc.state !== "released") continue;
    out.push({
      id: String(doc.id ?? ""),
      kind: String(doc.kind ?? ""),
      version: Number(doc.version ?? 0),
      body: String(doc.body ?? ""),
      sources: Array.isArray(doc.sources) ? doc.sources : [],
    });
  }
  return out;
}

export function presentMatters(payload: unknown): MatterRow[] {
  return rowsFrom(payload, "matters").flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    return [{
      id: String(row.id ?? ""),
      title: String(row.title ?? ""),
      jurisdiction: String(row.jurisdiction ?? ""),
      area: String(row.area ?? ""),
      status: String(row.status ?? ""),
      documents: releasedOnly(row.documents),
    }];
  });
}

export function reviewerMay(tags: string[], jurisdiction: string): boolean {
  if (jurisdiction === "both") return tags.includes("us") || tags.includes("za");
  return tags.includes(jurisdiction);
}

function cleanError(value: unknown): string | null {
  const text = String(value ?? "").trim();
  if (!text) return null;
  if (/token|secret|password|api[_-]?key|bearer/i.test(text)) return "The last load reported an error.";
  return text.slice(0, 240);
}

export function presentFeeds(payload: unknown): { region: string; sources: FeedRow[] } {
  const region = payload && typeof payload === "object" ? String((payload as Record<string, unknown>).region ?? "") : "";
  const sources = rowsFrom(payload, "sources").flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const row = item as Record<string, unknown>;
    const keyName = typeof row.key_name === "string" && row.key_name && row.key_name !== "none" ? row.key_name : "none";
    const keySet: FeedRow["key_set"] = keyName === "none" ? "no key" : row.key_set === true || row.key_set === "yes" ? "yes" : "no";
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
      key_name: keyName,
      key_set: keySet,
      documents: Number(row.documents ?? 0),
      last_load: typeof last === "string" ? last : null,
      errors,
    }];
  });
  return { region, sources };
}

export function presentReview(payload: unknown, tags: string[]): ReviewItem[] {
  const items = rowsFrom(payload, "items");
  const out: ReviewItem[] = [];
  for (const item of items) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const document = (row.document && typeof row.document === "object" ? row.document : row) as Record<string, unknown>;
    const matter = (row.matter && typeof row.matter === "object" ? row.matter : {}) as Record<string, unknown>;
    const jurisdiction = String(matter.jurisdiction ?? document.jurisdiction ?? "");
    if (!reviewerMay(tags, jurisdiction)) continue;
    const sources = Array.isArray(document.sources) ? document.sources.flatMap((source) => {
      if (!source || typeof source !== "object") return [];
      const entry = source as Record<string, unknown>;
      return [{ citation: String(entry.citation ?? entry.doc_id ?? ""), quote: String(entry.quote ?? "") }];
    }) : [];
    const matches = Array.isArray(row.matches) ? row.matches.flatMap((match) => {
      if (!match || typeof match !== "object") return [];
      const entry = match as Record<string, unknown>;
      const findings = Array.isArray(entry.element_findings)
        ? entry.element_findings.flatMap((finding) => {
            if (!finding || typeof finding !== "object") return [];
            const part = finding as Record<string, unknown>;
            const label = [part.element, part.finding].filter(Boolean).join(": ");
            return label ? [label] : [];
          })
        : [];
      return [{
        id: String(entry.id ?? ""),
        outcome: String(entry.outcome ?? ""),
        jurisdiction: String(entry.jurisdiction ?? ""),
        findings,
      }];
    }) : [];
    const documentId = String(document.id ?? "");
    if (!documentId) continue;
    out.push({
      documentId,
      body: String(document.body ?? ""),
      state: String(document.state ?? ""),
      sources,
      matterId: String(matter.id ?? document.matter_id ?? ""),
      title: String(matter.title ?? "Matter"),
      jurisdiction,
      area: String(matter.area ?? ""),
      matches,
    });
  }
  return out;
}
