import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Jost } from "next/font/google";
import "./globals.css";

const jost = Jost({
  subsets: ["latin"],
  weight: ["300", "400"],
  variable: "--font-jost",
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-jetbrains",
  display: "swap",
});

const description =
  "Tervory is one window where you ask for data, research, price checks, legal reviews or a website. Specialists do the work. Every answer comes back with the model that produced it and the price it cost — down to the fraction of a cent.";

export const metadata: Metadata = {
  metadataBase: new URL("https://tervory.com"),
  title: "Tervory AI — Ask for the work. See exactly what it cost.",
  description,
  openGraph: {
    title: "Tervory AI — Ask for the work. See exactly what it cost.",
    description,
    images: [{ url: "/og.png", width: 1200, height: 630 }],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${jost.variable} ${inter.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
