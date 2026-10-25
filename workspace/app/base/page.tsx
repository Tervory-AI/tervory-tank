import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { isFounder } from "@/lib/admin";
import { activeTenant } from "@/lib/tenant";
import { refreshBase } from "./actions";
import { askBase, searchBase } from "./search";
import { loadBase } from "./load";
import { loadBasePlugins } from "./vault-server";
import { BaseView } from "./view";
import "./base.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Base · Tervory",
  description:
    "Base fills in business records: website, email, phone, size and a short description. Every field shows where it came from and how sure Base is.",
};

/**
 * Public Base product host — Figma Base Command Post (ksi7ctRwEnN8wbip1yfuhL node 73:1950).
 * Own navy chrome (not app-shell). Batches/counts stay empty until Tank has live rows for the signed-in org.
 */
export default async function BasePublicPage() {
  const [model, plugins, tenant] = await Promise.all([loadBase(), loadBasePlugins(), activeTenant()]);
  const { userId } = await auth();
  return (
    <BaseView
      model={model}
      plugins={plugins}
      accountName={tenant?.orgName ?? null}
      refresh={refreshBase}
      search={searchBase}
      ask={askBase}
      canRunTrial={isFounder(userId)}
    />
  );
}
