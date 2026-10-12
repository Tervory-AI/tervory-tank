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

// ---- tasks: the board ----

export type TaskStatus = "queued" | "running" | "done" | "failed";

export type Task = {
  id: string;
  tenant_id: string;
  created_by: string | null;
  agent: string;
  task_type: string;
  title: string;
  status: TaskStatus;
  result: string | null;
  error: string | null;
  ledger_id: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  // joined from the ledger row once the task has run
  model?: string | null;
  rung?: number | null;
  cost_usd?: number | string | null;
  latency_ms?: number | null;
  feedback?: "accepted" | "rejected" | null;
};

export function createTask(
  tenantId: string,
  createdBy: string,
  title: string,
  taskType: string,
  messages: ChatMessage[],
): Promise<Task> {
  return tank<Task>("/v1/tasks", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, created_by: createdBy, title, task_type: taskType, messages }),
  });
}

export function listTasks(tenantId: string, limit = 50): Promise<Task[]> {
  return tank<Task[]>(`/v1/tasks?tenant_id=${tenantId}&limit=${limit}`, { method: "GET" });
}

// ---- feedback: the outcome column ----

export function sendFeedback(
  tenantId: string,
  ledgerId: string,
  feedback: "accepted" | "rejected",
  by: string,
  note?: string,
): Promise<{ ok: true }> {
  return tank<{ ok: true }>(`/v1/ledger/${ledgerId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, feedback, by, note: note ?? null }),
  });
}

// ---- ledger ----

export type LedgerSummary = {
  tenant_id: string;
  days: number;
  calls: number;
  delivered: number;
  accepted: number;
  rejected: number;
  acceptance_rate: number | null;
  cost_usd: number;
  cost_per_delivered_usd: number | null;
  cost_per_accepted_usd: number | null;
  by_model: {
    model: string;
    rung: number;
    calls: number;
    tokens_in: number;
    tokens_out: number;
    cost_usd: number;
    delivered: number;
    accepted: number;
    rejected: number;
  }[];
};

export function ledgerSummary(tenantId: string, days = 30): Promise<LedgerSummary> {
  return tank<LedgerSummary>(`/v1/ledger/summary?tenant_id=${tenantId}&days=${days}`, { method: "GET" });
}

// ---- Skala: skills ----

export type SkillState = "candidate" | "staging" | "approved" | "retired";
export type Skill = {
  id: string;
  version: string;
  agent: string;
  rung: number;
  task_type: string | null;
  description: string;
  state: SkillState;
  eval_threshold: number | string;
  cases: number;
  last_eval_score: number | string | null;
  last_eval_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  present: boolean;
};

export type EvalResult = {
  skill: string;
  passed: number;
  total: number;
  score: number;
  threshold: number;
  cost_usd: number;
  state: SkillState;
  gate: "passed" | "failed";
  details: { case: number; name: string | null; passed: boolean; why: string }[];
};

export function listSkills(): Promise<Skill[]> {
  return tank<Skill[]>("/v1/skills", { method: "GET" });
}
export function runSkillEvals(id: string, version: string, by: string): Promise<EvalResult> {
  return tank<EvalResult>(`/v1/skills/${encodeURIComponent(id)}/${encodeURIComponent(version)}/evals`, {
    method: "POST",
    body: JSON.stringify({ by }),
  });
}
export function approveSkill(id: string, version: string, by: string): Promise<{ ok: true }> {
  return tank<{ ok: true }>(`/v1/skills/${encodeURIComponent(id)}/${encodeURIComponent(version)}/approve`, {
    method: "POST",
    body: JSON.stringify({ by }),
  });
}
export function retireSkill(id: string, version: string, by: string): Promise<{ ok: true }> {
  return tank<{ ok: true }>(`/v1/skills/${encodeURIComponent(id)}/${encodeURIComponent(version)}/retire`, {
    method: "POST",
    body: JSON.stringify({ by }),
  });
}

// ---- Base: records ----

export type BaseRecord = {
  id: string;
  task_id: string | null;
  batch: string | null;
  raw: Record<string, unknown>;
  profile: Record<string, { value: unknown; source: string; confidence: number }>;
  passes: Record<string, Record<string, unknown>>;
  confidence: number;
  status: "queued" | "running" | "done" | "failed";
  error: string | null;
  created_at: string;
};

export function baseRun(
  tenantId: string, createdBy: string, batch: string, records: Record<string, unknown>[], preview: boolean,
  engine?: string | null, splitByState = false,
) {
  return tank<{ task: Task; tasks: Task[]; records: number; batches: number; skills: Record<string, string> }>("/v1/base/run", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, created_by: createdBy, batch, records, preview, engine: engine || null, split_by_state: splitByState }),
  });
}
export function baseEngines(): Promise<string[]> {
  return tank<string[]>("/v1/base/engines", { method: "GET" });
}
export function baseRecords(tenantId: string, opts: { taskId?: string; batch?: string; limit?: number; offset?: number } = {}): Promise<BaseRecord[]> {
  const q = new URLSearchParams({ tenant_id: tenantId, limit: String(opts.limit ?? 200), offset: String(opts.offset ?? 0) });
  if (opts.taskId) q.set("task_id", opts.taskId);
  if (opts.batch) q.set("batch", opts.batch);
  return tank<BaseRecord[]>(`/v1/base/records?${q}`, { method: "GET" });
}

export type BaseBatch = {
  batch: string; started: string; total: number; done: number; failed: number; pending: number;
  ready: number; aware: number; review: number; requeue: number; with_site: number; with_email: number;
};
export function baseRetry(tenantId: string, batch: string): Promise<{ requeued: number }> {
  return tank<{ requeued: number }>("/v1/base/retry", { method: "POST", body: JSON.stringify({ tenant_id: tenantId, batch }) });
}
export function baseBatches(tenantId: string): Promise<BaseBatch[]> {
  return tank<BaseBatch[]>(`/v1/base/batches?tenant_id=${tenantId}`, { method: "GET" });
}

// ---- Tank: the ladder (graduation) ----

export type Ladder = {
  task_type: string; rung: number; model: string; candidate_model: string | null; shadow_rate: number | string;
  previous_model: string | null; eval_threshold: number | string; cache_scope: string; priority: string;
  n: number; agreement: number | string | null; cand_cost: number | string | null; prim_cost: number | string | null;
  calls_30d: number; cost_30d: number | string; cache_hits: number; eligible: boolean; saving_pct: number | null;
};
export function ladder(): Promise<Ladder[]> {
  return tank<Ladder[]>("/v1/graduation", { method: "GET" });
}
export function setCandidate(taskType: string, candidateModel: string | null, shadowRate: number, by: string) {
  return tank<{ ok: true }>(`/v1/graduation/${encodeURIComponent(taskType)}/candidate`, {
    method: "PUT", body: JSON.stringify({ candidate_model: candidateModel, shadow_rate: shadowRate, by }),
  });
}
export function promoteCandidate(taskType: string, by: string) {
  return tank<{ ok: true; model: string }>(`/v1/graduation/${encodeURIComponent(taskType)}/promote`, { method: "POST", body: JSON.stringify({ by }) });
}
export function rollbackModel(taskType: string, by: string) {
  return tank<{ ok: true; model: string }>(`/v1/graduation/${encodeURIComponent(taskType)}/rollback`, { method: "POST", body: JSON.stringify({ by }) });
}
export type EvalsSummary = { task_type: string; cases: number; accepted: number; rejected: number; manual: number };
export function evalsSummary(): Promise<EvalsSummary[]> {
  return tank<EvalsSummary[]>("/v1/evals/summary", { method: "GET" });
}
