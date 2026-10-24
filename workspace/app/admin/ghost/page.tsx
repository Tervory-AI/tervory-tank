import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { ghostPanel } from "@/lib/tank";
import { look, resolve, shieldAction } from "./actions";
import { GhostConsole } from "./panel";
import { shieldBoard, type ShieldBoard } from "./shields-data";
import { ShieldsTile } from "./tile";

export const dynamic = "force-dynamic";

export default async function GhostPage() {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  const board: ShieldBoard | null = await shieldBoard(userId).catch(() => null);
  const tile = <ShieldsTile board={board} act={shieldAction} />;
  try {
    const data = await ghostPanel(userId);
    return <GhostConsole data={data} look={look} resolve={resolve} tile={tile} />;
  } catch {
    return <GhostConsole data={null} error="Ghost’s room is unavailable. Check the room and its Tank connection." look={look} resolve={resolve} tile={tile} />;
  }
}
