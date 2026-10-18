/** Drawn frame copy. Blanks stay blanks. These are not filed matters. */

export const AREAS = [
  "All areas (civil)",
  "Administrative",
  "Agricultural",
  "Animal welfare",
  "Arbitration and ADR",
  "Aviation",
  "Banking and finance",
  "Child law (civil)",
  "Competition",
  "Constitutional",
  "Construction",
  "Consumer",
  "Contract",
  "Corporate and commercial",
  "Customs and excise",
  "Cyber and data",
  "Defamation",
  "Delict",
  "Education",
  "Employment and labour",
  "Energy and mining",
  "Environmental",
  "Estates and wills",
  "Family (civil)",
  "Franchise",
  "Gambling and liquor",
  "Health",
  "Housing and rental",
  "Human rights (civil)",
  "Immigration",
  "Insolvency",
  "Insurance",
  "Intellectual property",
  "International trade",
  "Land and property",
  "Local government",
  "Maritime and shipping",
  "Media",
  "Medical negligence",
  "Motor vehicle accidents (RAF)",
  "Pensions",
  "Procurement",
  "Sectional title",
  "Sports",
  "Tax",
  "Telecoms",
  "Transport",
  "Trusts",
  "Water",
] as const;

export const COURTS = [
  "Any",
  "Constitutional Court",
  "Supreme Court of Appeal",
  "High Court",
  "Magistrates' Court",
  "Labour Court",
  "Land Claims Court",
  "Competition Tribunal",
  "Tax Court",
] as const;

export const SEARCH_KINDS = ["All", "Matters", "Drafts", "Documents", "Citations", "Review"] as const;
export type SearchKind = (typeof SEARCH_KINDS)[number];

export type SearchHit = {
  kind: Exclude<SearchKind, "All">;
  title: string;
  meta: string;
  status?: string;
};

export const SEARCH_HITS: SearchHit[] = [
  { kind: "Matters", title: "Case name v Case name", meta: "Matter · Area · Court · updated __ / __ / ____", status: "Status" },
  { kind: "Matters", title: "Case name v Case name", meta: "Matter · Area · Court · updated __ / __ / ____", status: "Status" },
  { kind: "Drafts", title: "Draft name · v__", meta: "Draft · Case name v Case name · __ / __ / ____", status: "Status" },
  { kind: "Drafts", title: "Draft name · v__", meta: "Draft · Case name v Case name · __ / __ / ____", status: "Status" },
  { kind: "Documents", title: "Document name.pdf", meta: "Document · __ pages · Annexure FA __" },
  { kind: "Citations", title: "[____] ZA____ __ at para __", meta: "Saved citation · Case name v Case name" },
  { kind: "Citations", title: "Act name No __ of ____, s __", meta: "Saved citation · Statute" },
  { kind: "Review", title: "Item name", meta: "Review · Reviewer · __ / __ / ____", status: "Status" },
];

export const MATTER_ROWS = 5;
export const REVIEW_ROWS = 2;
export const DEADLINE_ROWS = [
  { title: "Deadline name", meta: "__ / __ / ____ · Rule __" },
  { title: "Deadline name", meta: "__ / __ / ____ · Rule __" },
  { title: "Court date", meta: "__ / __ / ____ · Court" },
] as const;

/** Alert timings from the drawn Deadlines panel. These are not matters. */
export const DEADLINE_ALERTS = [
  { title: "5 court days before", detail: "Email and in-app, to the matter attorney" },
  { title: "1 court day before", detail: "Email, in-app and SMS, to the attorney and reviewer" },
  { title: "On the day", detail: "In-app banner on the lawyer review console" },
] as const;

export const DEADLINE_NOTE =
  "Rule periods are shown for design. A lawyer must confirm each rule card before deadlines go live.";

export function hitsFor(kind: SearchKind, query: string): SearchHit[] {
  const needle = query.trim().toLowerCase();
  return SEARCH_HITS.filter((hit) => {
    if (kind !== "All" && hit.kind !== kind) return false;
    if (!needle) return true;
    return `${hit.title} ${hit.meta} ${hit.status ?? ""}`.toLowerCase().includes(needle);
  });
}
