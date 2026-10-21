"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";
import { isFounder } from "@/lib/admin";
import { ghostLook, ghostResolve } from "@/lib/tank";

export type GhostResult = { ok: boolean; message: string } | null;

export async function look(_previous: GhostResult, form: FormData): Promise<GhostResult> {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) return { ok: false, message: "Not found." };
  const target = String(form.get("target") ?? "");
  const signal = String(form.get("signal") ?? "");
  try {
    const incident = await ghostLook(userId, target, signal);
    revalidatePath("/admin/ghost");
    return { ok: true, message: incident.summary ?? "The investigation has started." };
  } catch {
    return { ok: false, message: "Ghost could not finish the investigation. Check its room and Tank connection." };
  }
}

export async function resolve(_previous: GhostResult, form: FormData): Promise<GhostResult> {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) return { ok: false, message: "Not found." };
  const id = String(form.get("id") ?? "");
  const cause = String(form.get("cause") ?? "");
  const fix = String(form.get("fix") ?? "");
  try {
    await ghostResolve(userId, id, cause, fix);
    revalidatePath("/admin/ghost");
    return { ok: true, message: "The check passed. The confirmed cause and fix are saved." };
  } catch {
    return { ok: false, message: "The issue could not be verified. It has not been marked solved." };
  }
}
