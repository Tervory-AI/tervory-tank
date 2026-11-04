// Client workspaces from the repo, not from a founder click. Server-side only.
//
// The roster is names only: each client's Clerk organization name and the squad
// products it has on (ids from changeSquad in app/control/squad-actions.ts).
// reconcileClients() runs once per server start from instrumentation.ts; tests call
// it directly. Importing this file never runs it.

import "server-only";

import { clerkClient } from "@clerk/nextjs/server";
import { tenantIdFor, uuidFrom } from "./tenant";
import { caseStudyRequest, readCommandSquads, setCommandSquad } from "./tank";

export const CLIENT_ROSTER: ReadonlyArray<{ name: string; products: ReadonlyArray<string> }> = [
  { name: "Custom Nation", products: ["rig", "tiger"] },
  { name: "LOKD Security", products: ["radix"] },
  { name: "AmmoSync", products: ["base", "market_lab"] },
  { name: "Shot Bonus", products: [] },
  { name: "TNGO", products: [] },
];

type Clerk = Awaited<ReturnType<typeof clerkClient>>;
type Organization = { id: string; name: string };

/** Stable, provider-unique create identity across independent server instances. */
function clientSlug(name: string): string {
  return `tervory-client-${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

async function findOrganization(clerk: Clerk, name: string): Promise<Organization | null> {
  const matches = new Map<string, Organization>();
  // Check both the stable slug (including a renamed org) and legacy exact names.
  for (const query of [clientSlug(name), name]) {
    for (let offset = 0; ; ) {
      const page = await clerk.organizations.getOrganizationList({ query, limit: 100, offset });
      for (const org of page.data) {
        if (org.slug === clientSlug(name) || org.name === name) matches.set(org.id, org);
      }
      offset += page.data.length;
      if (page.data.length === 0 || offset >= page.totalCount) break;
    }
  }
  if (matches.size > 1) throw new Error("Ambiguous client organization");
  return matches.values().next().value ?? null;
}

async function organizationFor(clerk: Clerk, name: string, founder: string): Promise<Organization> {
  let org = await findOrganization(clerk, name);
  if (!org) {
    try {
      org = await clerk.organizations.createOrganization({ name, slug: clientSlug(name), createdBy: founder });
    } catch (error) {
      // A concurrent start or a response lost after create can already have won.
      // Never retry creation with a different slug or select a partial-name match.
      org = await findOrganization(clerk, name);
      if (!org) throw error;
    }
  }
  const memberships = await clerk.organizations.getOrganizationMembershipList({
    organizationId: org.id, userId: [founder], limit: 100,
  });
  if (!memberships.data.some(member => member.publicUserData?.userId === founder && member.role === "org:admin")) {
    throw new Error("Client organization is not founder administered");
  }
  return org;
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
  // Resolve all bindings before any Tank write so aliases cannot merge clients.
  const bindings: Array<{ client: typeof CLIENT_ROSTER[number]; orgId: string; tenantId: string }> = [];
  for (const client of CLIENT_ROSTER) {
    try {
      const org = await organizationFor(clerk, client.name, founder);
      bindings.push({ client, orgId: org.id, tenantId: tenantIdFor(org.id) });
    } catch (error) {
      console.warn("client_reconcile_failed", { client: client.name, error: errorClass(error) });
    }
  }
  for (const binding of bindings) {
    const { client } = binding;
    let orgId: string | undefined;
    let tenantId: string | undefined;
    try {
      orgId = binding.orgId;
      tenantId = binding.tenantId;
      if (tenantId !== uuidFrom(orgId) || bindings.filter(other => other.tenantId === tenantId).length !== 1) {
        throw new Error("Automatic client provisioning requires an unaliased, unique tenant");
      }
      // Request-time ensure is deliberately best-effort; startup must report a
      // failed registration rather than claim the client was reconciled.
      const response = await caseStudyRequest({ tenantId, userId: founder }, "ensure",
        new URLSearchParams(), AbortSignal.timeout(1500));
      if (!response.ok) throw new Error("Client registration failed");
      const { grants, log } = await readCommandSquads(founder, tenantId);
      for (const agent of client.products) {
        // Startup seeds missing products; it never undoes a founder's later removal.
        if (grants.some(grant => grant.agent === agent && grant.enabled)
          || log.some(change => change.agent === agent && !change.enabled)) continue;
        // The existing read returns at most 20 history rows. An absent agent's
        // removal may be older: fail closed instead of restoring that entitlement.
        if (log.length >= 20) throw new Error("Client grant history is incomplete");
        await setCommandSquad(founder, tenantId, agent, true);
      }
      console.info("client_reconciled", { client: client.name, orgId, tenantId });
    } catch (error) {
      console.warn("client_reconcile_failed", { client: client.name, orgId, tenantId, error: errorClass(error) });
    }
  }
}
