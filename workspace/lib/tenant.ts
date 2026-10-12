// Who is asking, and which tenant are they acting in.
//
// Tenant model (Build Pack v2, "Regions and tenancy"): one Clerk organization = one
// Tervory tenant. The organization id is the tenant_id stamped on every ledger row
// and every record. A user with no organization gets a personal one created on
// first use, so solo entrepreneurs never see a setup screen.
//
// Clerk org ids look like "org_2abc…"; Tank's ledger stores tenant_id as a UUID, so
// we derive a stable UUID (v5) from the org id. Same org, same UUID, every time.

import { auth, clerkClient, currentUser } from "@clerk/nextjs/server";
import { createHash } from "node:crypto";

export type Tenant = { tenantId: string; orgId: string; orgName: string; userId: string };

const NAMESPACE = "7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b"; // fixed; never change or tenant ids shift

/** Deterministic UUID v5 from an arbitrary string. */
export function uuidFrom(input: string): string {
  const ns = Buffer.from(NAMESPACE.replace(/-/g, ""), "hex");
  const h = createHash("sha1").update(ns).update(input).digest();
  h[6] = (h[6] & 0x0f) | 0x50; // version 5
  h[8] = (h[8] & 0x3f) | 0x80; // variant
  const hex = h.subarray(0, 16).toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** The current user's tenant. Creates a personal organization if they have none. */
export async function currentTenant(): Promise<Tenant> {
  const { userId, orgId } = await auth();
  if (!userId) throw new Error("not signed in");

  const client = await clerkClient();

  if (orgId) {
    // The session carries the org id and slug; the display name needs one lookup.
    const org = await client.organizations.getOrganization({ organizationId: orgId });
    return { tenantId: uuidFrom(orgId), orgId, orgName: org.name, userId };
  }

  // No active organization: use the first one they belong to, or create a personal one.
  const memberships = await client.users.getOrganizationMembershipList({ userId, limit: 1 });
  let org = memberships.data[0]?.organization;
  if (!org) {
    const user = await currentUser();
    const label = user?.firstName || user?.primaryEmailAddress?.emailAddress?.split("@")[0] || "My";
    org = await client.organizations.createOrganization({ name: `${label} workspace`, createdBy: userId });
  }
  return { tenantId: uuidFrom(org.id), orgId: org.id, orgName: org.name, userId };
}
