// Client workspaces from the repo, not from a founder click. Server-side only.
//
// The roster is names only: each client's Clerk organization name and the squad
// products it has on (ids from changeSquad in app/control/squad-actions.ts).
// reconcileClients() runs once per server start from instrumentation.ts; tests call
// it directly. Importing this file never runs it.

import { clerkClient } from "@clerk/nextjs/server";
import { tenantIdFor } from "./tenant";
import { ensureCaseStudyReports, setCommandSquad } from "./tank";

export const CLIENT_ROSTER: ReadonlyArray<{ name: string; products: ReadonlyArray<string> }> = [
  { name: "Custom Nation", products: ["rig", "tiger"] },
  { name: "LOKD Security", products: ["radix"] },
  { name: "AmmoSync", products: ["base", "market_lab"] },
  { name: "Shot Bonus", products: [] },
  { name: "TNGO", products: [] },
];

type Clerk = Awaited<ReturnType<typeof clerkClient>>;
type Organization = { id: string; name: string };

/** An existing organization with exactly this name, or null. Never creates one. */
async function findOrganization(clerk: Clerk, name: string): Promise<Organization | null> {
  for (let offset = 0; ; ) {
    const page = await clerk.organizations.getOrganizationList({ query: name, limit: 100, offset });
    const match = page.data.find((org) => org.name === name);
    if (match) return match;
    offset += page.data.length;
    if (page.data.length === 0 || offset >= page.totalCount) return null;
  }
}

function errorClass(error: unknown): string {
  return error instanceof Error ? error.constructor.name : typeof error;
}

/** Create any missing roster organization, register its tenant and turn its products on.
 *  Never renames, deletes or turns anything off. One client's failure never stops the rest;
 *  the next server start retries. Logs only client name, org id, tenant id and error class. */
export async function reconcileClients(): Promise<void> {
  const founder = (process.env["TERVORY_ADMIN_USER_IDS"] ?? "").split(",").map((part) => part.trim()).filter(Boolean)[0];
  if (!founder) {
    console.warn("client_reconcile_skipped_no_founder");
    return;
  }
  let clerk: Clerk;
  try {
    clerk = await clerkClient();
  } catch (error) {
    console.warn("client_reconcile_failed", { error: errorClass(error) });
    return;
  }
  for (const client of CLIENT_ROSTER) {
    let orgId: string | undefined;
    let tenantId: string | undefined;
    try {
      const org = (await findOrganization(clerk, client.name))
        ?? await clerk.organizations.createOrganization({ name: client.name, createdBy: founder });
      orgId = org.id;
      tenantId = tenantIdFor(org.id);
      await ensureCaseStudyReports({ tenantId, userId: founder });
      for (const agent of client.products) await setCommandSquad(founder, tenantId, agent, true);
      console.info("client_reconciled", { client: client.name, orgId, tenantId });
    } catch (error) {
      console.warn("client_reconcile_failed", { client: client.name, orgId, tenantId, error: errorClass(error) });
    }
  }
}
