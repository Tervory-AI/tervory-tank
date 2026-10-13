import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { Inter, JetBrains_Mono, Jost } from "next/font/google";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import "./admin.css";

const jost = Jost({ subsets: ["latin"], weight: "300", variable: "--font-jost", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export const dynamic = "force-dynamic";

export const metadata: Metadata = { title: "Founder console · Tervory" };

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth();
  if (!isFounder(userId)) notFound();
  return <div className={`tvy-admin ${jost.variable} ${inter.variable} ${mono.variable}`}>{children}</div>;
}
