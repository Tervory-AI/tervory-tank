"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "../review/founder";
import { writeFeedBatch } from "./quarantine-store";

const PLATFORM = "00000000-0000-0000-0000-000000000001";

async function founderId(): Promise<string | null> {
  try {
    const { userId } = await auth();
    if (!isListedFounder(userId, process.env.TERVORY_ADMIN_USER_IDS)) return null;
    return userId ?? null;
  } catch {
    return null;
  }
}

async function tellLab(batchId: string, action: "release" | "reject" | "remove"): Promise<void> {
  const key = process.env.TANK_KEY_MARKET_LAB ?? "";
  if (!key) return;
  const host = process.env.MARKET_LAB_URL ?? "http://agent-market-lab:8000";
  await fetch(`${host}/quarantine/${encodeURIComponent(batchId)}/${action}`, {
    method: "POST",
    headers: { "X-Tank-Key": key },
    cache: "no-store",
  });
}

async function tellTank(batchId: string, userId: string): Promise<void> {
  if (!process.env.TANK_API_KEY) return;
  const host = process.env.TANK_URL ?? "http://tank:8000";
  await fetch(`${host}/v1/training/batches/${encodeURIComponent(batchId)}/remove`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-tank-key": process.env.TANK_API_KEY,
      "x-tervory-user": userId,
      "x-tervory-tenant": PLATFORM,
      "x-tervory-role": "founder",
    },
    cache: "no-store",
  });
}

async function act(form: FormData, action: "release" | "reject" | "remove"): Promise<void> {
  const userId = await founderId();
  if (!userId) throw new Error("Not found");
  const batchId = String(form.get("batch") ?? "").trim();
  if (!batchId) throw new Error("Not found");
  await writeFeedBatch(batchId, action);
  try {
    await tellLab(batchId, action);
  } catch {
    // The feeds file is already changed. The box can be reached on the next try.
  }
  if (action === "remove") {
    try {
      await tellTank(batchId, userId);
    } catch {
      // Gold retirement is retried from Tank when the batch id is sent again.
    }
  }
  revalidatePath("/market-lab");
}

export async function releaseBatch(form: FormData): Promise<void> {
  await act(form, "release");
}

export async function rejectBatch(form: FormData): Promise<void> {
  await act(form, "reject");
}

export async function removeBatch(form: FormData): Promise<void> {
  await act(form, "remove");
}
