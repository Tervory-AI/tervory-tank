import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { activeTenant } from "@/lib/tenant";
import { isListedFounder } from "../review/founder";
import { refreshFeeds } from "./actions";
import { loadMarketLab } from "./load";
import { MarketLabView } from "./view";
import "./market-lab.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Market Lab · Tervory",
};

export default async function MarketLabPage() {
  const model = await loadMarketLab();
  let founder = false;
  let workspaceName: string | null = null;
  try {
    const { userId } = await auth();
    founder = isListedFounder(userId, process.env.TERVORY_ADMIN_USER_IDS);
    const tenant = await activeTenant();
    workspaceName = tenant?.orgName ?? null;
  } catch {
    founder = false;
    workspaceName = null;
  }
  return <MarketLabView model={model} refresh={refreshFeeds} founder={founder} workspaceName={workspaceName} />;
}
