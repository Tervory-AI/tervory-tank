import type { Metadata } from "next";
import { MarketLabPublic } from "./public-view";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Market Lab · Tervory",
  description: "Market Lab — readings and sourced reports from the feeds you run.",
};

export default function MarketLabPublicPage() {
  return <MarketLabPublic />;
}
