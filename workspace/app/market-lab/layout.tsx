import type { Metadata } from "next";
import "./market-lab.css";

export const metadata: Metadata = { title: "Market Lab · Tervory" };

export default function MarketLabLayout({ children }: { children: React.ReactNode }) {
  return children;
}
