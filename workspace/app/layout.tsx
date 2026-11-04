import type { Metadata } from "next";
import { TriggerSigninProvider } from "./trigger-signin-provider";
import { auth } from "@/lib/trigger-signin";
import { isListedFounder } from "./review/founder";
import { Shell, type ShellAccess } from "./shell";
import { inter, jost, mono } from "./fonts";
import "./globals.css";

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
    // SigninDirectory 7 (Core 3): ClerkProvider sits inside <body>, not around <html>.
    <html lang="en" className={`${jost.variable} ${inter.variable} ${mono.variable}`}>
      <body>
        <TriggerSigninProvider>
          <Shell founder={access.founder} reviewer={access.reviewer} readAccess={readAccess}>{children}</Shell>
        </TriggerSigninProvider>
      </body>
    </html>
  );
}
