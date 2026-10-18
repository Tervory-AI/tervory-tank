import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { inter, jost, mono } from "../brand-fonts";
import "./admin.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Founder console · Tervory" };

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth();
  if (!isFounder(userId)) notFound();
  return <div className={`tvy-admin ${jost.variable} ${inter.variable} ${mono.variable}`}>{children}</div>;
}
