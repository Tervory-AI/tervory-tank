import type { Metadata } from "next";
import { BaseDocument } from "./public-doc";
import "../product-public.css";
import "./public.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Base · Tervory",
  description: "Base — a typed document with colour. Write, highlight, keep the brief.",
};

/** Public Base product — typed document surface. No auth wall. */
export default function BasePublicPage() {
  return <BaseDocument />;
}
