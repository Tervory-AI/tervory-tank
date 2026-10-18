import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { offLibrary, offPanel } from "./plugins";
import { loadSkillLibrary, loadSkalaPlugins } from "./vault-server";
import { SkalaApp } from "./view";
import "./skala.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = { title: "Skala · Tervory" };

export default async function SkalaPage() {
  let accountName: string | null = null;
  let signedIn = false;
  try {
    const tenant = await activeTenant();
    signedIn = Boolean(tenant);
    accountName = tenant?.orgName ?? null;
  } catch {
    accountName = null;
  }
  const plugins = signedIn ? await loadSkalaPlugins() : offPanel("Sign in to use Plugins.");
  const library = signedIn ? await loadSkillLibrary() : offLibrary();
  return <SkalaApp accountName={accountName} plugins={plugins} library={library} />;
}
