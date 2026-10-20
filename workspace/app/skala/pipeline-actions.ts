"use server";

import { revalidatePath } from "next/cache";
import { activeTenant } from "@/lib/tenant";
import { librarySkills, transferLibrarySkill, vaultPlugins, VAULT_OFF_MESSAGE } from "@/lib/tank";
import { AGENTS, TANK_WAITS, TRANSFER_WAITS } from "./pipelines";

export type TransferResult = { waiting: boolean; message: string };

const LIBRARY_WAITS = "The skills library is off. The transfer waits.";

export async function transferToAgent(squad: string, skillId: string, version: string): Promise<TransferResult> {
  const agent = AGENTS.find((row) => row.squad === squad);
  if (!agent) return { waiting: true, message: "That agent is not on this page. Nothing was copied." };
  const tenant = await activeTenant();
  if (!tenant) return { waiting: true, message: "Sign in to use a pipeline." };
  if (agent.holds || !agent.vault) return { waiting: true, message: TANK_WAITS };

  let enabled = false;
  try {
    const raw = await vaultPlugins(agent.vault, agent.squad, tenant.tenantId, tenant.userId);
    enabled = Boolean(raw.enabled);
  } catch (error) {
    const text = error instanceof Error ? error.message : "";
    if (text.includes(VAULT_OFF_MESSAGE) || !enabled) return { waiting: true, message: TRANSFER_WAITS };
    return { waiting: true, message: TRANSFER_WAITS };
  }
  if (!enabled) return { waiting: true, message: TRANSFER_WAITS };

  let skills: { skill_id?: string; version?: string }[] = [];
  let libraryOn = false;
  try {
    const library = await librarySkills("skala", tenant.tenantId, tenant.userId);
    libraryOn = Boolean(library.enabled);
    skills = library.skills ?? [];
  } catch {
    return { waiting: true, message: LIBRARY_WAITS };
  }
  if (!libraryOn) return { waiting: true, message: LIBRARY_WAITS };
  const skill = skills.find((row) => row.skill_id === skillId && row.version === version);
  if (!skill?.skill_id || !skill.version) {
    return { waiting: true, message: "That skill is not in the library. Nothing was copied." };
  }
  try {
    await transferLibrarySkill(agent.squad, tenant.tenantId, tenant.userId, skill.skill_id, skill.version);
  } catch (error) {
    const text = error instanceof Error ? error.message : "";
    if (text.includes(VAULT_OFF_MESSAGE)) return { waiting: true, message: TRANSFER_WAITS };
    return { waiting: true, message: "The transfer waits. Nothing was copied." };
  }
  revalidatePath("/skala");
  return { waiting: false, message: `Copied into ${agent.label}. The library was left as it is.` };
}
