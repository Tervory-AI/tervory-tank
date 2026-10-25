import type { Metadata } from "next";
import { TigerPublic } from "./public-view";
import "../product-public.css";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Tiger · Tervory",
  description: "Tiger — price watches and stock alerts across the shelves you care about.",
};

/** Public Tiger product — watches and alerts. No auth wall. */
export default function TigerPublicPage() {
  return <TigerPublic />;
}
