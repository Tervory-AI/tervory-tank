"use server";
import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { revalidatePath } from "next/cache";
import { isFounder } from "@/lib/admin";
import { setPaidPause, switchProvenModel } from "@/lib/tank";

async function founder(): Promise<string> {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  return userId;
}
export async function pauseAction(paused: boolean): Promise<{ error?: string }> {
  const userId = await founder();
  try { await setPaidPause(userId, paused); revalidatePath("/control"); return {}; }
  catch { return { error: "The pause could not be changed. Refresh to check its current state." }; }
}
export async function switchAction(taskType: string): Promise<{ error?: string }> {
  const userId = await founder();
  try { await switchProvenModel(userId, taskType); revalidatePath("/control"); return {}; }
  catch { return { error: "The switch was refused or could not be confirmed. Refresh to check the current model." }; }
}
