import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { ghostPanel } from "@/lib/tank";
import { look, resolve, shieldAction } from "./actions";
import { AutumbraConsole } from "./panel";
import { shieldBoard, type ShieldBoard } from "./shields-data";
import { ShieldsTile } from "./tile";

export const dynamic = "force-dynamic";

export default async function AutumbraPage() {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  const board: ShieldBoard | null = await shieldBoard(userId).catch(() => null);
  const tile = <ShieldsTile board={board} act={shieldAction} />;
  try {
    const data = await ghostPanel(userId);
    return <AutumbraConsole data={data} look={look} resolve={resolve} tile={tile} showFixtures />;
  } catch {
    return (
      <AutumbraConsole
        data={null}
        error="Autumbra’s room is unavailable. Fixture board below still works — sign-out visitors use /autumbra/demo."
        look={look}
        resolve={resolve}
        tile={tile}
        showFixtures
      />
    );
  }
}
