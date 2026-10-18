// Server-only. The browser does not call Tank, and it never receives a secret value.

import { activeTenant } from "@/lib/tenant";
import { librarySkills, vaultPlugins, VAULT_OFF_MESSAGE } from "@/lib/tank";
import { mapLibraryPayload, mapVaultPayload, offLibrary, offPanel, type LibraryPanel, type PluginPanel } from "./plugins";

const VAULT = "skala.vault";
const SQUAD = "skala";

export async function loadSkalaPlugins(): Promise<PluginPanel> {
  const tenant = await activeTenant();
  if (!tenant) return offPanel("Sign in to use Plugins.");
  try {
    const raw = await vaultPlugins(VAULT, SQUAD, tenant.tenantId, tenant.userId);
    return mapVaultPayload(raw);
  } catch (error) {
    const text = error instanceof Error ? error.message : "";
    if (text.includes(VAULT_OFF_MESSAGE)) return offPanel();
    return offPanel("Plugins could not be loaded from Tank. No vault data is shown.");
  }
}

export async function loadSkillLibrary(): Promise<LibraryPanel> {
  const tenant = await activeTenant();
  if (!tenant) return offLibrary();
  try {
    const raw = await librarySkills(SQUAD, tenant.tenantId, tenant.userId);
    return mapLibraryPayload(raw);
  } catch {
    return offLibrary();
  }
}
