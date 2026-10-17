import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "../review/founder";
import { RadixPage } from "./view";
import "./radix.css";

export const metadata: Metadata = {
  title: "Radix | Tervory",
  description: "Review code checks, findings, and reports.",
};

export default async function Page() {
  const { userId } = await auth();
  return <RadixPage founder={isListedFounder(userId, process.env["TERVORY_ADMIN_USER_IDS"])} />;
}
