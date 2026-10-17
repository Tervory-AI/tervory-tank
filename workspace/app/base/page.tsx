import type { Metadata } from "next";
import { auth } from "@clerk/nextjs/server";
import { isListedFounder } from "../review/founder";
import { refreshBase } from "./actions";
import { loadBase } from "./load";
import { askBase, searchBase } from "./search";
import { BaseView } from "./view";
import "./base.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = {
  title: "Base · Tervory",
};

export default async function BasePage() {
  const { userId } = await auth();
  const founder = isListedFounder(userId, process.env["TERVORY_ADMIN_USER_IDS"]);
  const model = await loadBase();
  return <BaseView model={model} founder={founder} refresh={refreshBase} search={searchBase} ask={askBase} />;
}
