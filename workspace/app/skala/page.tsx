import type { Metadata } from "next";
import { SkalaPublic } from "./public-view";
import "../product-public.css";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Skala · Tervory",
  description: "Skala — skills library with eval scores and approval state.",
};

export default function SkalaPublicPage() {
  return <SkalaPublic />;
}
