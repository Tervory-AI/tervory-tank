"use server";

import { activeTenant } from "@/lib/tenant";
import { approveTisanGold, tisanGoldPages } from "@/lib/tank";

async function founder() {
  const tenant = await activeTenant();
  const allowed = (process.env.TERVORY_ADMIN_USER_IDS ?? "").split(",").map((id) => id.trim()).filter(Boolean);
  if (!tenant || !allowed.includes(tenant.userId)) throw new Error("Not available");
  return tenant;
}

export async function loadGoldPages() {
  const tenant = await founder();
  return tisanGoldPages(tenant.tenantId, tenant.userId);
}

export async function approveGoldPage(pageId: string, frameHash: string, pageHash: string) {
  const tenant = await founder();
  if (!/^[a-z0-9-]{1,100}$/.test(pageId) || !/^[a-f0-9]{64}$/.test(frameHash) || !/^[a-f0-9]{64}$/.test(pageHash))
    throw new Error("Invalid page reference");
  await approveTisanGold(tenant.tenantId, tenant.userId, pageId, frameHash, pageHash);
  return { approved: true };
}
