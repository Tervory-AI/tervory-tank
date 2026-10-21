"use server";
import { proofResponse } from "./server";
import type { RowFilter, SavingsRows } from "./savings-types";

export async function readFounderSavingsRows(tenant: string, filters: RowFilter): Promise<SavingsRows> {
  const query: Record<string, string> = { tenant_id: tenant, end: filters.end, page: String(filters.page ?? 0) };
  for (const name of ["start", "until", "member", "population"] as const) if (filters[name]) query[name] = String(filters[name]);
  if (filters.free_only) query.free_only = "true";
  return (await proofResponse(query, undefined, "/savings/rows")).json();
}
