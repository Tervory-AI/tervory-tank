import type { Metadata } from "next";
import { onbBody, onbHeading, onbMono } from "../brand-fonts";
import "./onboarding.css";

export const metadata: Metadata = {
  title: "Get started · Tervory",
  description: "Create an organization, add a CSV, and start your first run.",
};

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${onbBody.variable} ${onbHeading.variable} ${onbMono.variable} onboard`} style={{ minHeight: "100vh" }}>
      {children}
    </div>
  );
}
