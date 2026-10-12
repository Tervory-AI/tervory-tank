// The only way the Workspace talks to a model: through Tank.
// Server-side only (uses TANK_API_KEY). Never import from a client component.

const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type RouteResult = {
  ledger_id: string;
  model: string;
  rung: number;
  content: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  latency_ms: number;
};

async function tank<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${TANK_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", "x-tank-key": TANK_API_KEY, ...(init.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Tank ${path} ${res.status}: ${text.slice(0, 300)}`);
  }
  return (await res.json()) as T;
}

export function route(tenantId: string, taskType: string, messages: ChatMessage[], agent = "tier0"): Promise<RouteResult> {
  return tank<RouteResult>("/v1/route", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, agent, task_type: taskType, messages }),
  });
}

export type LedgerSummary = {
  tenant_id: string;
  days: number;
  calls: number;
  delivered: number;
  cost_usd: number;
  cost_per_delivered_usd: number | null;
  by_model: { model: string; rung: number; calls: number; tokens_in: number; tokens_out: number; cost_usd: number; delivered: number }[];
};

export function ledgerSummary(tenantId: string, days = 30): Promise<LedgerSummary> {
  return tank<LedgerSummary>(`/v1/ledger/summary?tenant_id=${tenantId}&days=${days}`, { method: "GET" });
}
