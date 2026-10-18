import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { modelRows } from "./models";
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
  return <TankView workspaceName={workspaceName} models={modelRows(process.env)} />;
}
