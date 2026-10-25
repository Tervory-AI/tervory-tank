import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { LEDE } from "./copy";
import { loadTiger } from "./load";
import { sectionFrom } from "./model";
import { loadTigerPlugins } from "./vault-server";
import { TigerApp } from "./view";
import "./tiger.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Tiger · Tervory",
  description: LEDE,
};

/**
 * Public Tiger product host — Figma Tiger Overview (ksi7ctRwEnN8wbip1yfuhL node 71:241).
 * Own navy chrome (not app-shell). Watches/alerts stay empty until Tank has live rows for the signed-in org.
 */
export default async function TigerPublicPage({
  searchParams,
}: {
  searchParams: Promise<{ tab?: string; notice?: string }>;
}) {
  const params = await searchParams;
  const [loaded, plugins, tenant] = await Promise.all([loadTiger(), loadTigerPlugins(), activeTenant()]);
  const notice = typeof params.notice === "string" && params.notice.trim() ? params.notice : loaded.notice ?? "";
  return (
    <TigerApp
      data={loaded.data}
      notice={notice}
      initialTab={sectionFrom(params.tab)}
      plugins={plugins}
      accountName={tenant?.orgName ?? null}
    />
  );
}
