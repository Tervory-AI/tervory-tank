import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { offPanel } from "./plugins";
import { loadZenasPlugins } from "./vault-server";
import { ZenasView } from "./view";
import "./zenas.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Zenas · Tervory",
};

export default async function ZenasPage() {
  let workspaceName: string | null = null;
  let signedIn = false;
  try {
    const tenant = await activeTenant();
    signedIn = Boolean(tenant);
    workspaceName = tenant?.orgName ?? null;
  } catch {
    workspaceName = null;
  }
  const plugins = signedIn ? await loadZenasPlugins() : offPanel("Sign in to use Plugins.");
  return <ZenasView plugins={plugins} workspaceName={workspaceName} />;
}
