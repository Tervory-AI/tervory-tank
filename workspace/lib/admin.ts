// Founder console. Server-side only. Never import this from a client component.
// The Workspace key stays here. Tank answers 404 unless the Clerk user id is listed.

const TANK_URL = process.env["TANK_URL"] ?? "http://tank:8000";
const TANK_API_KEY = process.env["TANK_API_KEY"] ?? "";

export type Metrics = {
  calls: number;
  spend_usd: number;
  outcomes: number;
  booked_usd: number;
  margin_pct: number | null;
  cost_per_outcome: number | null;
  proven_pct: number | null;
  off_paid_pct: number | null;
  independence_pct: number | null;
};

export type RouteEvidence = {
  task_type: string;
  model: string;
  rung: number;
  eval_score: number | null;
  shadow_agreement: number | null;
  shadow_n: number;
  acceptance_rate: number | null;
  proven: boolean;
  proven_at: string | null;
  lost_at: string | null;
  flag: string | null;
};

export type Counters = {
  note: string;
  lifetime: Metrics;
  last_30_days: Metrics;
  previous_30_days: Metrics;
  change: {
    proven_pct: number | null;
    off_paid_pct: number | null;
    independence_pct: number | null;
    margin_pct: number | null;
    booked_usd: number;
    spend_usd: number;
    cost_per_outcome: number | null;
  };
  routes: RouteEvidence[];
};

export type Point = {
  day: string;
  key: string;
  calls: number;
  proven_calls: number;
  off_paid_calls: number;
  calls_by_rung: { "1": number; "2": number; "3": number; "4": number };
  spend_usd: number;
  outcomes: number;
  booked_usd: number;
  margin_pct: number | null;
  cost_per_outcome: number | null;
  proven_pct: number | null;
  off_paid_pct: number | null;
  independence_pct: number | null;
};

export type Total = {
  key: string;
  calls: number;
  spend_usd: number;
  outcomes: number;
  booked_usd: number;
  margin_pct: number | null;
  cost_per_outcome: number | null;
  proven_pct: number | null;
  off_paid_pct: number | null;
  independence_pct: number | null;
};

export type Series = { days: number; group: string; points: Point[]; totals: Total[] };

export type FocusRow = {
  task_type: string;
  model: string;
  rung: number;
  calls: number;
  spend_usd: number;
  share_of_paid_spend_pct: number;
  cache_hit_rate_pct: number | null;
  candidate_model: string | null;
  agreement: number | null;
  sample_size: number;
  min_samples: number;
  status: "unproven" | "testing" | "ready to promote" | "proven";
  next_step: string;
  eval_score: number | null;
  acceptance_rate: number | null;
};

export type Graduation = {
  id: string;
  at: string;
  day: string;
  task_type: string;
  action: string;
  from_model: string | null;
  to_model: string | null;
  saving_pct: number | null;
};

export type PriceRow = {
  id: string;
  tenant_id: string | null;
  outcome_type: string;
  unit_price: number;
  currency: string;
  effective_from: string | null;
  effective_to: string | null;
  note: string | null;
  current: boolean;
};

export function isFounder(userId: string | null | undefined): boolean {
  if (!userId) return false;
  const raw = process.env["TERVORY_ADMIN_USER_IDS"] ?? "";
  const allowed = raw.split(",").map((part) => part.trim()).filter((part) => part.length > 0);
  return allowed.includes(userId);
}

async function adminFetch<T>(userId: string, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${TANK_URL}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "x-tank-key": TANK_API_KEY,
      "x-tervory-admin": userId,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (res.status === 404) {
    throw new Error("Tank does not list this user as a founder. Set TERVORY_ADMIN_USER_IDS on Tank to the same Clerk user id.");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`The console could not load (${res.status}). ${text.slice(0, 180)}`);
  }
  return (await res.json()) as T;
}

export function loadFounder(userId: string, days: number): Promise<{
  counters: Counters;
  taskSeries: Series;
  agentSeries: Series;
  focus: FocusRow[];
  graduations: Graduation[];
  prices: PriceRow[];
}> {
  return Promise.all([
    adminFetch<Counters>(userId, "/v1/admin/counters"),
    adminFetch<Series>(userId, `/v1/admin/series?days=${days}&group=task_type`),
    adminFetch<Series>(userId, `/v1/admin/series?days=${days}&group=agent`),
    adminFetch<FocusRow[]>(userId, `/v1/admin/focus?days=${days}`),
    adminFetch<Graduation[]>(userId, `/v1/admin/graduations?days=${days}`),
    adminFetch<PriceRow[]>(userId, "/v1/admin/price_book"),
  ]).then(([counters, taskSeries, agentSeries, focus, graduations, prices]) => ({
    counters, taskSeries, agentSeries, focus, graduations, prices,
  }));
}

export function savePrice(
  userId: string,
  body: { outcome_type: string; unit_price: number; currency: string; note: string | null },
): Promise<PriceRow> {
  return adminFetch<PriceRow>(userId, "/v1/admin/price_book", { method: "PUT", body: JSON.stringify(body) });
}
