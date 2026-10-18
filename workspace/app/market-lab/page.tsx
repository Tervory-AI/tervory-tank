import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { refreshFeeds } from "./actions";
import { readFlags, loadMarketLab } from "./load";
import { offPanel } from "./plugins";
import { loadLabPlugins, resolveLabFeedKey } from "./vault-server";
import { MarketLabView } from "./view";
import "./market-lab.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Market Lab · Tervory",
};

export default async function MarketLabPage() {
  let workspaceName: string | null = null;
  let signedIn = false;
  try {
    const tenant = await activeTenant();
    signedIn = Boolean(tenant);
    workspaceName = tenant?.orgName ?? null;
  } catch {
    workspaceName = null;
  }
  const plugins = signedIn ? await loadLabPlugins() : offPanel("Sign in to use Plugins.");
  const envKeys = readFlags();
  const model = await loadMarketLab({
    vault: { enabled: plugins.enabled, names: plugins.enabled ? plugins.secrets.map((row) => row.name) : [] },
    resolveKey: plugins.enabled ? resolveLabFeedKey : undefined,
  });
  return (
    <MarketLabView
      model={model}
      plugins={plugins}
      envKeys={envKeys}
      refresh={refreshFeeds}
      workspaceName={workspaceName}
    />
  );
}
