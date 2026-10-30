// Existing Clerk session authority only; no browser body/header supplies a role.
import { auth } from "@clerk/nextjs/server";
import { tenantIdFor, type Tenant } from "./tenant";

export async function triggerIdentity(tenant: Tenant | null): Promise<(Tenant & { tenantAdmin: boolean }) | null> {
  if (!tenant) return null;
  const session = await auth();
  const tenantAdmin = session.userId === tenant.userId && session.orgId === tenant.orgId
    && tenantIdFor(tenant.orgId) === tenant.tenantId && session.orgRole === "org:admin";
  return { ...tenant, tenantAdmin };
}
