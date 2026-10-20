"use server";
import { revalidatePath } from "next/cache";
import { goldIdentity } from "../skala/gold/access";
import { promoteCandidate, trainingGraduation } from "@/lib/tank";

export async function promoteTraining(form: FormData) {
  const identity = await goldIdentity("platform");
  if (identity.role !== "founder") throw new Error("Not found");
  const task = String(form.get("task") ?? "");
  const rows = await trainingGraduation(identity);
  if (!rows.some(row => row.task_type === task && row.can_promote)) throw new Error("Candidate is not ready");
  // Existing Tank endpoint independently enforces the live shadow bar.
  await promoteCandidate(task, identity.userId);
  revalidatePath("/tank");
}
