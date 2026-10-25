import type { Metadata } from "next";
import { RadixPublic } from "./public-view";
import "../product-public.css";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Radix · Tervory",
  description: "Radix — review findings, severity, and the release brief.",
};

export default function RadixPublicPage() {
  return <RadixPublic />;
}
