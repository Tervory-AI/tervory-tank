const PLATFORM = "00000000-0000-0000-0000-000000000001";
type OrganisationPage = { data: { id: string; name: string }[]; totalCount: number };

/** Resolve only this box's tenant IDs; never expose unrelated organisations. */
export async function resolveTenantNames(
  tenantIds: string[],
  listPage: (params: { limit: number; offset: number; orderBy: "name" }) => Promise<OrganisationPage>,
  tenantIdFor: (orgId: string) => string,
): Promise<{ tenant_names: Record<string, string>; tenant_names_note: string | null }> {
  const names: Record<string, string> = { [PLATFORM]: "Tervory" };
  const missing = new Set(tenantIds.filter(id => id !== PLATFORM));
  try {
    let offset = 0;
    while (missing.size) {
      const page = await listPage({ limit: 100, offset, orderBy: "name" });
      for (const org of page.data) {
        const id = tenantIdFor(org.id);
        if (missing.has(id) && org.name.trim()) {
          names[id] = org.name;
          missing.delete(id);
        }
      }
      offset += page.data.length;
      if (!page.data.length || offset >= page.totalCount) break;
    }
  } catch { /* Keep evidence available; explicitly label missing names below. */ }
  [...missing].sort().forEach((id, index) => { names[id] = `Name unavailable (${index + 1})`; });
  return { tenant_names: names, tenant_names_note: missing.size ? "Some tenant names could not be loaded or matched to an organisation." : null };
}
