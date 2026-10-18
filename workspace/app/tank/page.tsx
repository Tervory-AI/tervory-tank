import type { Metadata } from "next";
import { listRoster } from "@/lib/tank";
import { activeTenant } from "@/lib/tenant";
import type { ModelRow } from "./squads";
import { TankView } from "./view";
import "./tank.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Tank · Tervory",
};

export default async function TankPage() {
  let workspaceName: string | null = null;
  try {
    const tenant = await activeTenant();
    workspaceName = tenant?.orgName ?? null;
  } catch {
    workspaceName = null;
  }
  let models: ModelRow[] = [];
  let modelsUnavailable = false;
  try {
    models = await listRoster();
  } catch {
    modelsUnavailable = true;
  }
  return <TankView workspaceName={workspaceName} models={models} modelsUnavailable={modelsUnavailable} />;
}
