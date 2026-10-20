import { activeTenant } from "@/lib/tenant";
import { offPanel, type PluginPanel } from "./vault-model";
import { loadTisanPlugins } from "./vault-server";
import { Tisan } from "./tisan";

export const dynamic = "force-dynamic";

export default async function TisanPage() {
  let plugins: PluginPanel = offPanel();
  let accountName: string | null = null;
  try {
    plugins = await loadTisanPlugins();
  } catch {
    plugins = offPanel("Plugins could not be loaded from Tank. No vault data is shown.");
  }
  try {
    accountName = (await activeTenant())?.orgName ?? null;
  } catch {
    accountName = null;
  }
  return <Tisan plugins={plugins} accountName={accountName} />;
}
