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

export type RosterModel = { name: string };

/** Names on the roster Tank already loads. No key and no missing-key flag. */
export async function listRoster(): Promise<RosterModel[]> {
  const rows = await tank<unknown>("/v1/models", { method: "GET" });
  if (!Array.isArray(rows)) return [];
  const models: RosterModel[] = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const record = row as Record<string, unknown>;
    const name = typeof record.name === "string" ? record.name.trim() : "";
    if (!name) continue;
    models.push({ name });
  }
  return models;
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
  agent = "tier0",
): Promise<Task> {
  return tank<Task>("/v1/tasks", {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, created_by: createdBy, title, task_type: taskType, messages, agent }),
  });
}

export function listTasks(tenantId: string, limit = 50): Promise<Task[]> {
  return tank<Task[]>(`/v1/tasks?tenant_id=${tenantId}&limit=${limit}`, { method: "GET" });
}

export function getTask(tenantId: string, taskId: string): Promise<Task> {
  const query = new URLSearchParams({ tenant_id: tenantId });
  return tank<Task>(`/v1/tasks/${encodeURIComponent(taskId)}?${query}`, { method: "GET" });
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

export type LedgerFailure = { day: string; task_type: string; skill: string; reason: string; calls: number; avg_ms: number | string | null; example: string | null };
export function ledgerFailures(tenantId: string, days = 30): Promise<LedgerFailure[]> {
  return tank<LedgerFailure[]>(`/v1/ledger/failures?tenant_id=${tenantId}&days=${days}`, { method: "GET" });
}

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
  details: { case: number; name: string | null; passed: boolean; why: string; goal: unknown; result: unknown }[];
};

export function listSkills(): Promise<Skill[]> {
  return tank<Skill[]>("/v1/skala", { method: "GET" });
}
export function runSkillEvals(id: string, version: string, by: string): Promise<EvalResult> {
  return tank<EvalResult>(`/v1/skala/${encodeURIComponent(id)}/${encodeURIComponent(version)}/evals`, {
    method: "POST",
    body: JSON.stringify({ by }),
  });
}
// Owner testing: run one skill version on one input, without touching any records.
export function trySkill(tenantId: string, id: string, version: string, input: Record<string, unknown>) {
  return tank<Record<string, unknown>>(`/v1/skala/${encodeURIComponent(id)}/run`, {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, version, input, preview: true }),
  });
}
export function approveSkill(id: string, version: string, by: string): Promise<{ ok: true }> {
  return tank<{ ok: true }>(`/v1/skala/${encodeURIComponent(id)}/${encodeURIComponent(version)}/approve`, {
    method: "POST",
    body: JSON.stringify({ by }),
  });
}
export function retireSkill(id: string, version: string, by: string): Promise<{ ok: true }> {
  return tank<{ ok: true }>(`/v1/skala/${encodeURIComponent(id)}/${encodeURIComponent(version)}/retire`, {
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
  model_skipped?: number;
};
export function baseRetry(tenantId: string, batch: string): Promise<{ requeued: number }> {
  return tank<{ requeued: number }>("/v1/base/retry", { method: "POST", body: JSON.stringify({ tenant_id: tenantId, batch }) });
}
export function baseRerun(
  tenantId: string, batch: string, flag = "no_website", preview?: boolean, skill?: string,
): Promise<{ requeued: number }> {
  return tank<{ requeued: number }>("/v1/base/rerun", {
    method: "POST", body: JSON.stringify({ tenant_id: tenantId, batch, flag, preview: preview ?? null, skill: skill || null }),
  });
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

// ---- Tiger: watches, prices, alerts (server-side; Tank proxies to the Tiger room) ----

export type TigerWatch = {
  id: string;
  tenant_id: string;
  url: string;
  label: string;
  engine: string;
  every: string;
  enabled: boolean;
  threshold: number | string;
};

export type TigerObservation = {
  id: string;
  tenant_id: string;
  url: string;
  ts: string;
  price: string | number | null;
  currency: string | null;
  availability: string | null;
  method: string | null;
  evidence: string | null;
};

export type TigerAlert = {
  id: string;
  tenant_id: string;
  url: string;
  ts: string;
  kind: string;
  before: string | null;
  after: string | null;
};

async function tigerCall<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${TANK_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", "x-tank-key": TANK_API_KEY, ...(init.headers ?? {}) },
    cache: "no-store",
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Tank ${path} ${res.status}: ${text.slice(0, 300)}`);
  }
  if (!text) return null as T;
  return JSON.parse(text) as T;
}

export function listTigerWatches(tenantId: string): Promise<{ watches: TigerWatch[] }> {
  return tigerCall<{ watches: TigerWatch[] }>(`/v1/tiger/watchlist?tenant_id=${encodeURIComponent(tenantId)}`, { method: "GET" });
}

export function createTigerWatch(
  tenantId: string,
  input: { url: string; label: string; every: string; threshold: number },
): Promise<TigerWatch> {
  return tigerCall<TigerWatch>("/v1/tiger/watchlist", {
    method: "POST",
    body: JSON.stringify({
      tenant_id: tenantId,
      url: input.url,
      label: input.label,
      every: input.every,
      threshold: input.threshold,
      enabled: true,
      engine: "",
    }),
  });
}

export function deleteTigerWatch(tenantId: string, watchId: string): Promise<null> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return tigerCall<null>(`/v1/tiger/watchlist/${encodeURIComponent(watchId)}?${q}`, { method: "DELETE" });
}

export function listTigerObservations(tenantId: string, url: string): Promise<{ observations: TigerObservation[] }> {
  const q = new URLSearchParams({ tenant_id: tenantId, url });
  return tigerCall<{ observations: TigerObservation[] }>(`/v1/tiger/observations?${q}`, { method: "GET" });
}

export function listTigerAlerts(tenantId: string, url?: string): Promise<{ alerts: TigerAlert[] }> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  if (url) q.set("url", url);
  return tigerCall<{ alerts: TigerAlert[] }>(`/v1/tiger/alerts?${q}`, { method: "GET" });
}

// ---- Plugins vaults. Server-side only. The browser never receives a secret value. ----

export const VAULT_OFF_MESSAGE = "This vault is off. Turn it on in Tank.";

export type VaultPlugins = {
  vault: string;
  enabled: boolean;
  message: string | null;
  secrets: { name: string; purpose: string; mask: string; saved_at: string }[];
  files: { id: string; name: string; type: string; size: number; rows: number | null; pages: number | null; uploaded_at: string; status: string }[];
  links: { id: string; url: string; label: string; frequency: string; last_checked: string | null; status: string }[];
  connections: { id: string; name: string; server_url: string; auth_type: string; status: string; last_used: string | null; has_token: boolean }[];
};

async function vaultFetch(path: string, userId: string, squad: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("x-tank-key", TANK_API_KEY);
  headers.set("x-tervory-user", userId);
  headers.set("x-tervory-squad", squad);
  if (typeof init.body === "string" && !headers.has("content-type")) headers.set("content-type", "application/json");
  return fetch(`${TANK_URL}${path}`, { ...init, headers, cache: "no-store" });
}

async function vaultJson<T>(path: string, userId: string, squad: string, init: RequestInit): Promise<T> {
  const res = await vaultFetch(path, userId, squad, init);
  const text = await res.text();
  if (!res.ok) throw new Error(`Tank ${path} ${res.status}: ${text.slice(0, 180)}`);
  return (text ? JSON.parse(text) : {}) as T;
}

export function vaultPlugins(vault: string, squad: string, tenantId: string, userId: string): Promise<VaultPlugins> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return vaultJson<VaultPlugins>(`/v1/vaults/${encodeURIComponent(vault)}/plugins?${q}`, userId, squad, { method: "GET" });
}

export function saveVaultSecret(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  name: string,
  purpose: string,
  value: string,
): Promise<{ ok: boolean }> {
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/secrets`, userId, squad, {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, name, purpose, value }),
  });
}

export function removeVaultSecret(vault: string, squad: string, tenantId: string, userId: string, name: string): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({ tenant_id: tenantId, name });
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/secrets?${q}`, userId, squad, { method: "DELETE" });
}

/** Server-only. Do not pass the result to a client component. */
export async function resolveVaultSecret(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  name: string,
): Promise<string | null> {
  const body = await vaultJson<{ found?: boolean; value?: string }>(
    `/v1/vaults/${encodeURIComponent(vault)}/secrets/resolve`,
    userId,
    squad,
    { method: "POST", body: JSON.stringify({ tenant_id: tenantId, name }) },
  );
  return body.found && typeof body.value === "string" ? body.value : null;
}

export async function uploadVaultFiles(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  files: FormData,
): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  const res = await vaultFetch(`/v1/vaults/${encodeURIComponent(vault)}/files?${q}`, userId, squad, {
    method: "POST",
    body: files,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`Tank /files ${res.status}: ${text.slice(0, 180)}`);
  return { ok: true };
}

export function removeVaultFile(vault: string, squad: string, tenantId: string, userId: string, fileId: string): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/files/${encodeURIComponent(fileId)}?${q}`, userId, squad, {
    method: "DELETE",
  });
}

export function addVaultLink(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  url: string,
  label: string,
  frequency: string,
): Promise<{ ok: boolean }> {
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/links`, userId, squad, {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, url, label, frequency }),
  });
}

export function removeVaultLink(vault: string, squad: string, tenantId: string, userId: string, linkId: string): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/links/${encodeURIComponent(linkId)}?${q}`, userId, squad, {
    method: "DELETE",
  });
}

export function addVaultConnection(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  name: string,
  serverUrl: string,
  authType: string,
  token: string,
): Promise<{ ok: boolean }> {
  return vaultJson(`/v1/vaults/${encodeURIComponent(vault)}/connections`, userId, squad, {
    method: "POST",
    body: JSON.stringify({ tenant_id: tenantId, name, server_url: serverUrl, auth_type: authType, token }),
  });
}

export function removeVaultConnection(
  vault: string,
  squad: string,
  tenantId: string,
  userId: string,
  connectionId: string,
): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return vaultJson(
    `/v1/vaults/${encodeURIComponent(vault)}/connections/${encodeURIComponent(connectionId)}?${q}`,
    userId,
    squad,
    { method: "DELETE" },
  );
}

// Skills library. library.vault is not skala.vault. Server-side only.
// A squad may list, link, or transfer. It cannot rewrite the library from here.

export type LibrarySkill = {
  skill_id: string;
  version: string;
  agent: string;
  description: string;
  published_at: string | null;
};

export type LibraryLink = {
  id: string;
  squad: string;
  vault: string;
  skill_id: string;
  version: string;
  created_at: string | null;
};

export type LibraryView = {
  vault: string;
  enabled: boolean;
  message: string | null;
  skills: LibrarySkill[];
  links: LibraryLink[];
};

export function librarySkills(squad: string, tenantId: string, userId: string): Promise<LibraryView> {
  const q = new URLSearchParams({ tenant_id: tenantId });
  return vaultJson<LibraryView>(`/v1/vaults/library.vault/skills?${q}`, userId, squad, { method: "GET" });
}

export function linkLibrarySkill(
  squad: string,
  tenantId: string,
  userId: string,
  skillId: string,
  version: string,
): Promise<{ id: string; vault: string }> {
  return vaultJson(
    `/v1/vaults/library.vault/skills/${encodeURIComponent(skillId)}/${encodeURIComponent(version)}/link`,
    userId,
    squad,
    { method: "POST", body: JSON.stringify({ tenant_id: tenantId }) },
  );
}

export function transferLibrarySkill(
  squad: string,
  tenantId: string,
  userId: string,
  skillId: string,
  version: string,
): Promise<{ ok: boolean; vault: string }> {
  return vaultJson(
    `/v1/vaults/library.vault/skills/${encodeURIComponent(skillId)}/${encodeURIComponent(version)}/transfer`,
    userId,
    squad,
    { method: "POST", body: JSON.stringify({ tenant_id: tenantId }) },
  );
}

// Gold review: identity and tenant come only from the authenticated server route.
export function goldSummary(identity: { userId: string; tenantId: string; role: string }): Promise<{
  region: string;
  skills: Array<{ agent: string; skill_id: string; checked: number; target: number; holdout: number; candidates: number; last_score: number | null; trend: number | null; ran_at: string | null }>;
  pairs: Record<string, number>;
}> {
  return tank("/v1/gold/summary", { method: "GET", headers: {
    "x-tervory-user": identity.userId, "x-tervory-tenant": identity.tenantId, "x-tervory-role": identity.role,
  } });
}

export function goldNext(identity: { userId: string; tenantId: string; role: string }, agent: string, skill: string, after?: string): Promise<{
  id: string; input: unknown; expected: Record<string, unknown>; source: string;
} | null> {
  const query = new URLSearchParams({ agent, skill });
  if (after) query.set("after", after);
  return tank(`/v1/gold/next?${query}`, { method: "GET", headers: {
    "x-tervory-user": identity.userId, "x-tervory-tenant": identity.tenantId, "x-tervory-role": identity.role,
  } });
}

export function checkGold(identity: { userId: string; tenantId: string; role: string }, id: string,
  body: { action: "right" | "wrong" | "skip"; correction?: Record<string, unknown>; note?: string }): Promise<{ ok: boolean }> {
  return tank(`/v1/gold/${encodeURIComponent(id)}/check`, { method: "POST", body: JSON.stringify(body), headers: {
    "x-tervory-user": identity.userId, "x-tervory-tenant": identity.tenantId, "x-tervory-role": identity.role,
  } });
}

export function confirmTrainingRead(identity: { userId: string; tenantId: string; role: string }, observationId: string): Promise<{ ok: boolean }> {
  return tank(`/v1/training/tiger/${encodeURIComponent(observationId)}/confirm`, { method: "POST", headers: {
    "x-tervory-user": identity.userId, "x-tervory-tenant": identity.tenantId, "x-tervory-role": identity.role,
  } });
}

export function finalGoldCheck(identity: { userId: string; tenantId: string; role: string }, skill: string, version: string): Promise<{
  results: Array<{ skill_id: string; version: string; score: number; n: number }>;
}> {
  return tank(`/v1/gold/final/${encodeURIComponent(skill)}/${encodeURIComponent(version)}`, { method: "POST", headers: {
    "x-tervory-user": identity.userId, "x-tervory-tenant": identity.tenantId, "x-tervory-role": identity.role,
  } });
}

// Stripe event ids. The Workspace key is the only caller. A repeat claim is first: false.
export function claimBillingEvent(eventId: string, type: string): Promise<{ first: boolean }> {
  return tank<{ first: boolean }>("/v1/billing/events/claim", {
    method: "POST",
    body: JSON.stringify({ event_id: eventId, type }),
  });
}

export function releaseBillingEvent(eventId: string): Promise<{ released: boolean }> {
  return tank<{ released: boolean }>("/v1/billing/events/release", {
    method: "POST",
    body: JSON.stringify({ event_id: eventId }),
  });
}

export function markBillingEventHandled(eventId: string): Promise<{ handled: boolean }> {
  return tank<{ handled: boolean }>("/v1/billing/events/handled", {
    method: "POST",
    body: JSON.stringify({ event_id: eventId }),
  });
}

export type TisanGoldPage = {
  page_id: string; tenant_id: string; figma_file_id: string; figma_frame_id: string;
  built_page_path: string; frame_hash: string; page_hash: string;
  frame: Record<string, unknown>; page_structure: Record<string, unknown>; html: string; css: string;
};

export function tisanGoldPages(tenantId: string, userId: string): Promise<TisanGoldPage[]> {
  return tank<TisanGoldPage[]>(`/v1/tisan/gold/pages?tenant_id=${encodeURIComponent(tenantId)}`, {
    method: "GET", headers: { "X-Tervory-Admin": userId },
  });
}

export function approveTisanGold(tenantId: string, userId: string, pageId: string, frameHash: string, pageHash: string) {
  return tank<{ approved: boolean }>("/v1/tisan/gold/approve", {
    method: "POST", headers: { "X-Tervory-Admin": userId },
    body: JSON.stringify({ tenant_id: tenantId, page_id: pageId, frame_hash: frameHash, page_hash: pageHash }),
  });
}
