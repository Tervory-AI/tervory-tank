import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { isFounder } from "@/lib/admin";
import { publicScores } from "@/app/api/zenas/feeds/public";
import { homeRegion, zenasIn } from "@/app/api/zenas/tank";
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
  let founderLine: string | null = null;
  try {
    const { userId } = await auth();
    if (isFounder(userId)) {
      const region = homeRegion();
      const res = await zenasIn(region, `selftest?home_region=${region}`, { method: "GET" });
      const runs = res && res.ok ? publicScores(await res.json()).runs : [];
      const hold = runs.filter((row) => row.kind === "holdout");
      const top = hold[0];
      founderLine = top
        ? `Test scores: ${top.outcome_agreement}% outcome, ${top.cases} cases`
        : "Test scores";
    }
  } catch {
    founderLine = null;
  }
  return <ZenasView plugins={plugins} workspaceName={workspaceName} founderLine={founderLine} />;
}
