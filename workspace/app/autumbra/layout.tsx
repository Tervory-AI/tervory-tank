import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Autumbra · Watch + Enforce · Tervory",
  description:
    "Autumbra is onsite first-line defence: Watch finds issues, Enforce acts with your approval. Zero-ingestion — we never see your client data.",
};

export default function AutumbraLayout({ children }: { children: ReactNode }) {
  return children;
}
