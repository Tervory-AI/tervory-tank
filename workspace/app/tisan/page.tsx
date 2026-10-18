import { offPanel, type PluginPanel } from "./vault-model";
import { loadTisanPlugins } from "./vault-server";
import { Tisan } from "./tisan";

export const dynamic = "force-dynamic";

export default async function TisanPage() {
  let plugins: PluginPanel = offPanel();
  try {
    plugins = await loadTisanPlugins();
  } catch {
    plugins = offPanel("Plugins could not be loaded from Tank. No vault data is shown.");
  }
  return <Tisan plugins={plugins} />;
}
