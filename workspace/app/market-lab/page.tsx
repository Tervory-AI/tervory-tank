import type { Metadata } from "next";
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
  return <MarketLabView model={model} refresh={refreshFeeds} />;
}
