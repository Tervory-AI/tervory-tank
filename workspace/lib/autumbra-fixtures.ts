/** Fixture board for Autumbra demo — no live HF / Tank. Autumbra Watch + Enforce only. */

export type TriageItem = {
  id: string;
  target: string;
  signal: string;
  state: "needs_review" | "investigating" | "proposed" | "solved" | "blocked";
  summary: string;
  severity: "critical" | "high" | "medium" | "low";
  created_at: string;
  cost_usd: number;
  steps: { step: string; ledger_id: string; cost_usd: number }[];
};

export type InventoryItem = {
  id: string;
  name: string;
  ecosystem: "npm" | "pip" | "apt" | "docker";
  version: string;
  site: string;
  fingerprint: string;
};

export type AdvisoryItem = {
  id: string;
  cve: string;
  package: string;
  severity: "critical" | "high" | "medium" | "low";
  confidence: number;
  summary: string;
  matched_inventory_id: string;
  state: "open" | "proposed" | "shielded" | "dismissed";
};

export type EnforceAction = {
  id: string;
  kind: "shield" | "patch_brief" | "dry_run";
  title: string;
  site: string;
  state: "proposed" | "dry_run" | "up" | "undone" | "refused";
  plain: string;
  expression?: string;
};

export const DEMO_TRIAGE: TriageItem[] = [
  {
    id: "tri-1001",
    target: "workspace",
    signal: "certificate",
    state: "needs_review",
    summary: "TLS certificate for app.tervory.com expires in 11 days. Watch proposes renew-before-window.",
    severity: "high",
    created_at: "2026-10-25T06:12:00Z",
    cost_usd: 0.0042,
    steps: [
      { step: "health_probe", ledger_id: "led_a1", cost_usd: 0.0008 },
      { step: "cert_read", ledger_id: "led_a2", cost_usd: 0.0011 },
      { step: "triage_rank", ledger_id: "led_a3", cost_usd: 0.0023 },
    ],
  },
  {
    id: "tri-1002",
    target: "site",
    signal: "headers",
    state: "proposed",
    summary: "Missing Content-Security-Policy on marketing apex. Enforce has a shield dry-run ready.",
    severity: "medium",
    created_at: "2026-10-25T05:40:00Z",
    cost_usd: 0.0029,
    steps: [
      { step: "header_scan", ledger_id: "led_b1", cost_usd: 0.001 },
      { step: "threat_payload_burn", ledger_id: "led_b2", cost_usd: 0.0004 },
      { step: "propose_shield", ledger_id: "led_b3", cost_usd: 0.0015 },
    ],
  },
  {
    id: "tri-1003",
    target: "rig",
    signal: "advisory",
    state: "investigating",
    summary: "Inventory match: lodash@4.17.20 ↔ GHSA demo advisory. Patch brief drafted; not merged.",
    severity: "critical",
    created_at: "2026-10-25T04:05:00Z",
    cost_usd: 0.0071,
    steps: [
      { step: "inventory_fingerprint", ledger_id: "led_c1", cost_usd: 0.0012 },
      { step: "advisory_match", ledger_id: "led_c2", cost_usd: 0.0024 },
      { step: "patch_brief", ledger_id: "led_c3", cost_usd: 0.0035 },
    ],
  },
];

export const DEMO_INVENTORY: InventoryItem[] = [
  {
    id: "inv-1",
    name: "lodash",
    ecosystem: "npm",
    version: "4.17.20",
    site: "rig.tervory.com",
    fingerprint: "npm:lodash@4.17.20#fp_demo_91",
  },
  {
    id: "inv-2",
    name: "next",
    ecosystem: "npm",
    version: "15.2.4",
    site: "app.tervory.com",
    fingerprint: "npm:next@15.2.4#fp_demo_22",
  },
  {
    id: "inv-3",
    name: "requests",
    ecosystem: "pip",
    version: "2.31.0",
    site: "tank.tervory.com",
    fingerprint: "pip:requests@2.31.0#fp_demo_77",
  },
  {
    id: "inv-4",
    name: "nginx",
    ecosystem: "docker",
    version: "1.27.1",
    site: "protect.tervory.com",
    fingerprint: "docker:nginx@1.27.1#fp_demo_44",
  },
];

export const DEMO_ADVISORIES: AdvisoryItem[] = [
  {
    id: "adv-1",
    cve: "DEMO-2026-4411",
    package: "lodash",
    severity: "critical",
    confidence: 0.92,
    summary: "Prototype pollution in demo fixture range. Match is inventory-only; no source uploaded.",
    matched_inventory_id: "inv-1",
    state: "proposed",
  },
  {
    id: "adv-2",
    cve: "DEMO-2026-1188",
    package: "requests",
    severity: "medium",
    confidence: 0.71,
    summary: "TLS verification edge case in older minor. Watch ranked medium; Enforce standing by.",
    matched_inventory_id: "inv-3",
    state: "open",
  },
  {
    id: "adv-3",
    cve: "DEMO-2026-0902",
    package: "nginx",
    severity: "low",
    confidence: 0.54,
    summary: "Header parsing noise. Below auto-propose bar; kept visible for honesty.",
    matched_inventory_id: "inv-4",
    state: "open",
  },
];

export const DEMO_ENFORCE: EnforceAction[] = [
  {
    id: "enf-1",
    kind: "dry_run",
    title: "CSP shield · marketing apex",
    site: "tervory.com",
    state: "dry_run",
    plain: "Practice run: would add a managed Content-Security-Policy rule at the edge. Nothing changed.",
    expression: "(http.host eq \"tervory.com\" and not http.response.headers[\"content-security-policy\"])",
  },
  {
    id: "enf-2",
    kind: "patch_brief",
    title: "Bump lodash 4.17.20 → 4.17.21",
    site: "rig.tervory.com",
    state: "proposed",
    plain: "Open a dependency bump PR on the dogfood lockfile. Autumbra never merges.",
  },
  {
    id: "enf-3",
    kind: "shield",
    title: "Rate-limit repeated POSTs on /api",
    site: "app.tervory.com",
    state: "proposed",
    plain: "Propose a rate-limit shield. Raise only after health check passes.",
    expression: "(http.request.uri.path contains \"/api\" and rate(10m) > 400)",
  },
];
