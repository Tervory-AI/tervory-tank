import type { Metadata } from "next";
import { activeTenant } from "@/lib/tenant";
import { RadixSettings } from "./settings";
import { RadixPage } from "./view";
import "./radix.css";

export const metadata: Metadata = {
  title: "Radix | Tervory",
  description: "Review code checks, findings, and reports.",
};

export default async function Page() {
  const tenant = await activeTenant();
  return <RadixPage accountName={tenant?.orgName ?? "Choose an account"} settings={<RadixSettings />} />;
}
