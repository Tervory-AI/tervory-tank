import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { ghostPanel } from "@/lib/tank";
import { look, resolve } from "./actions";
import { GhostConsole } from "./panel";

export const dynamic = "force-dynamic";

export default async function GhostPage() {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  try {
    const data = await ghostPanel(userId);
    return <GhostConsole data={data} look={look} resolve={resolve} />;
  } catch {
    return <GhostConsole data={null} error="Ghost’s room is unavailable. Check the room and its Tank connection." look={look} resolve={resolve} />;
  }
}
