import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { Inter, JetBrains_Mono, Jost } from "next/font/google";
import { isListedFounder } from "./review/founder";
import { Shell, type ShellAccess } from "./shell";
import "./globals.css";

const jost = Jost({ subsets: ["latin"], weight: "300", variable: "--font-jost", display: "swap" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Tervory",
  description: "Ask for work. See what it cost.",
};

async function accessForRequest(): Promise<ShellAccess> {
  const { userId, orgRole } = await auth();
  const founder = isListedFounder(userId, process.env["TERVORY_ADMIN_USER_IDS"]);
  const role = (orgRole ?? "").replace(/^org:/, "");
  return { founder, reviewer: role === "reviewer" };
}

async function readAccess(): Promise<ShellAccess> {
  "use server";
  return accessForRequest();
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const access = await accessForRequest();
  return (
    <ClerkProvider>
      <html lang="en" className={`${jost.variable} ${inter.variable} ${mono.variable}`}>
        <body>
          <Shell founder={access.founder} reviewer={access.reviewer} readAccess={readAccess}>{children}</Shell>
        </body>
      </html>
    </ClerkProvider>
  );
}
