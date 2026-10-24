import { rigAdminPanel } from "@/lib/tank";
import { retailerIdentity } from "./actions";
import { RetailerAdmin } from "./retailer-admin";
import type { RetailerPanel } from "./types";
import "./retailer-admin.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Retailer settings · Rig" };

export default async function RetailerAdminPage() {
  let panel: RetailerPanel;
  try {
    panel = await rigAdminPanel<RetailerPanel>(await retailerIdentity());
  } catch {
    return <main className="retailer-admin"><a href="/rig">← Back to Rig</a><h1>Retailer settings</h1><p role="alert">Retailer settings are unavailable. Sign in as your retailer’s administrator and check that Rig is connected.</p></main>;
  }
  return <RetailerAdmin initial={panel} />;
}
