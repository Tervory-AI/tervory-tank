import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "./review/founder";
import { Shell } from "./shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tervory",
  description: "Ask for work. See what it cost.",
};

async function founderForRequest(): Promise<boolean> {
  const { userId } = await auth();
  return isListedFounder(userId, process.env["TERVORY_ADMIN_USER_IDS"]);
}

async function readFounder(): Promise<boolean> {
  "use server";
  return founderForRequest();
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const founder = await founderForRequest();
  return (
    <ClerkProvider>
      <html lang="en">
        <body>
          <Shell founder={founder} readFounder={readFounder}>{children}</Shell>
        </body>
      </html>
    </ClerkProvider>
  );
}
