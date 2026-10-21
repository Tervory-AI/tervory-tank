import "server-only";
import { goldIdentity } from "../../skala/gold/access";
import { notFound } from "next/navigation";
import type { Proof } from "./view";

export async function proofResponse(task?: string, format?: "csv" | "pdf") {
  const identity = await goldIdentity("platform");
  if (identity.role !== "founder") notFound();
  const query = new URLSearchParams({ tenant_id: identity.tenantId });
  if (task) query.set("task", task);
  const response = await fetch(`${process.env.TANK_URL ?? "http://tank:8000"}/v1/proof${format ? `/export/${format}` : ""}?${query}`, {
    cache: "no-store",
    headers: { "x-tank-key": process.env.TANK_API_KEY ?? "", "x-tervory-admin": identity.userId },
  });
  if (!response.ok) throw new Error("Proof evidence is unavailable. Try again when Tank is reachable.");
  return response;
}

export async function readProof(task?: string): Promise<Proof> {
  return (await proofResponse(task)).json();
}
