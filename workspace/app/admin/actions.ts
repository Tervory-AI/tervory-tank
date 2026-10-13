"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@clerk/nextjs/server";
import { isFounder, savePrice as putPrice } from "@/lib/admin";

export type SaveResult = { ok: true } | { ok: false; error: string };

export async function savePrice(_prev: SaveResult | null, formData: FormData): Promise<SaveResult> {
  const { userId } = await auth();
  if (!isFounder(userId) || !userId) return { ok: false, error: "Not found" };
  const outcomeType = String(formData.get("outcome_type") ?? "").trim();
  const unitPrice = Number(formData.get("unit_price"));
  const currency = String(formData.get("currency") ?? "USD").trim().toUpperCase();
  const note = String(formData.get("note") ?? "").trim();
  if (!outcomeType) return { ok: false, error: "Enter an outcome type." };
  if (!Number.isFinite(unitPrice) || unitPrice < 0) return { ok: false, error: "Enter a price that is zero or more." };
  if (!/^[A-Z]{3}$/.test(currency)) return { ok: false, error: "Currency is a three-letter code." };
  try {
    await putPrice(userId, { outcome_type: outcomeType, unit_price: unitPrice, currency, note: note || null });
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "The price could not be saved." };
  }
  revalidatePath("/admin");
  return { ok: true };
}
