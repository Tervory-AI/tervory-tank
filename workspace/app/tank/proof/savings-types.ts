export type Totals = { spent: string; would_have_cost: string; saved: string; work_count: number; jobs_count: number; free_count: number };
export type Savings = { as_of: string; revision: string; total: Totals; month: Totals; daily: (Totals & { day: string; cumulative: string })[]; members: (Totals & { member: string })[] };
export type RowFilter = { end: string; start?: string; until?: string; member?: string; free_only?: boolean; page?: number; population?: "eligible" | "excluded" | "costs" };
export type SavingsRows = { rows: { job_id: string | null; job_title: string | null; member: string; day: string; spent: string | null; would_have_cost: string | null; saved: string | null; free_work: boolean; id?: string; model?: string; excluded_reason?: string }[]; total: Totals; page: number; has_more: boolean; as_of: string };
export type Cost = { actual: string; baseline: string; unknown_costs: number; unknown_baselines: number };
export type FounderSavings = Savings & { tenant_id: string; tenants: string[]; region: string; excluded: { excluded_reason: string; count: number }[]; margin: { status: string; paid: null; margin: null; margin_percent: null; total: Cost; daily: (Cost & { day: string })[] } };
export const dollars = (value: string | number | null) => {
  if (value === null) return "Not available";
  const text = typeof value === "number" ? value.toFixed(8) : value;
  const [whole, fraction = ""] = text.split(".");
  return `$${whole}.${fraction.replace(/0+$/, "").padEnd(2, "0")}`;
};
/** Fixed eight-decimal receipt units; charts use numbers only for SVG coordinates. */
export const sumAmounts = (values: string[]) => {
  const units = values.reduce((sum, value) => {
    const [whole, fraction = ""] = value.split(".");
    return sum + BigInt(whole || "0") * BigInt(100000000) + BigInt(fraction.padEnd(8, "0"));
  }, BigInt(0));
  return `${units / BigInt(100000000)}.${String(units % BigInt(100000000)).padStart(8, "0")}`;
};
