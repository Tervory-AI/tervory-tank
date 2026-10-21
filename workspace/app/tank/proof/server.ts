import "server-only";
import { goldIdentity } from "../../skala/gold/access";
import { notFound } from "next/navigation";
import type { Proof } from "./view";

export type ProofFilters = { tenant_id?: string; task?: string; start?: string; end?: string; page?: string };

export async function proofResponse(filters: ProofFilters = {}, format?: "csv" | "pdf") {
  const identity = await goldIdentity("platform");
  if (identity.role !== "founder") notFound();
  const query = new URLSearchParams();
  for (const key of ["tenant_id", "task", "start", "end", "page"] as const) {
    const value = filters[key];
    if (!value || (key === "tenant_id" && value === "all")) continue;
    query.set(key, (key === "start" || key === "end") && !/(Z|[+-]\d\d:\d\d)$/.test(value) ? `${value}Z` : value);
  }
  const response = await fetch(`${process.env.TANK_URL ?? "http://tank:8000"}/v1/proof${format ? `/export/${format}` : ""}?${query}`, {
    cache: "no-store",
    headers: { "x-tank-key": process.env.TANK_API_KEY ?? "", "x-tervory-admin": identity.userId },
  });
  if (!response.ok) throw new Error("Proof evidence is unavailable. Try again when Tank is reachable.");
  return response;
}

export async function readProof(filters: ProofFilters = {}): Promise<Proof> {
  return (await proofResponse(filters)).json();
}
