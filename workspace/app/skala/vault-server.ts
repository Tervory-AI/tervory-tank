// Server-only. The browser does not call Tank, and it never receives a secret value.

import { activeTenant } from "@/lib/tenant";
import { librarySkills, vaultPlugins, VAULT_OFF_MESSAGE } from "@/lib/tank";
import { AGENTS, waitingPipelines, type PipelineDestination } from "./pipelines";
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

export async function loadPipelines(): Promise<PipelineDestination[]> {
  const tenant = await activeTenant();
  if (!tenant) return waitingPipelines();
  return Promise.all(AGENTS.map(async (agent) => {
    if (agent.holds || !agent.vault) {
      return { squad: agent.squad, label: agent.label, logo: agent.logo, enabled: false, waits: true };
    }
    try {
      const raw = await vaultPlugins(agent.vault, agent.squad, tenant.tenantId, tenant.userId);
      const enabled = Boolean(raw.enabled);
      return { squad: agent.squad, label: agent.label, logo: agent.logo, enabled, waits: !enabled };
    } catch {
      return { squad: agent.squad, label: agent.label, logo: agent.logo, enabled: false, waits: true };
    }
  }));
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
