import type { Metadata } from "next";

export const metadata: Metadata = {
  robots: { index: false, follow: false },
  title: "Internal",
  description: "Internal page. Not published.",
  openGraph: {
    title: "Internal",
    description: "Internal page. Not published.",
  },
};

export default function InternalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
