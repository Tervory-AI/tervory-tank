import type { Metadata } from "next";
import { TankPublic } from "./public-view";
import "./public.css";

export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: "Tank · Tervory",
  description: "Tank — roster, queue workers, and task receipts.",
};

export default function TankPublicPage() {
  return <TankPublic />;
}
