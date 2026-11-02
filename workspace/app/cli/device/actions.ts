"use server";

import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { triggerIdentity } from "@/lib/trigger";
import { deviceApproval, deviceCode, deviceRegion } from "@/lib/device-login";

/** Approve or deny one CLI sign-in code for the signed-in user's active org. */
export async function decideDevice(form: FormData): Promise<void> {
  const tenant = await triggerIdentity(await activeTenant());
  if (!tenant) redirect("/onboarding");
  const code = deviceCode(form.get("code"));
  const region = deviceRegion(form.get("region"));
  const choice = form.get("action");
  const action = choice === "approve" ? "approve" : choice === "deny" ? "deny" : null;
  if (!code || !region || !action) redirect("/cli/device?result=invalid");
  const result = await deviceApproval(tenant, region, code, action);
  redirect(`/cli/device?result=${result.ok ? result.device.status : "failed"}`);
}
