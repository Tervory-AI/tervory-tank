import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Jost } from "next/font/google";
import "./onboarding.css";

const body = Inter({ subsets: ["latin"], variable: "--onb-body" });
const heading = Jost({ subsets: ["latin"], weight: "300", variable: "--onb-heading" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: "400", variable: "--onb-mono" });

export const metadata: Metadata = {
  title: "Get started · Tervory",
  description: "Create an organization, add a CSV, and start your first run.",
};

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${body.variable} ${heading.variable} ${mono.variable} onboard`} style={{ minHeight: "100vh" }}>
      {children}
    </div>
  );
}
