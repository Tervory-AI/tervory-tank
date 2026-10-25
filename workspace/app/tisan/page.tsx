import type { Metadata } from "next";
import { TisanPublic } from "./public-view";
import "../product-public.css";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Tisan · Tervory",
  description: "Tisan — briefs and chats that stay with the work.",
};

export default function TisanPublicPage() {
  return <TisanPublic />;
}
