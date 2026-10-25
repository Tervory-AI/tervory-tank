import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { ghostPanel } from "@/lib/tank";
import { look, resolve, shieldAction } from "./actions";
import { AutumbraConsole } from "./panel";
import { shieldBoard, type ShieldBoard } from "./shields-data";
import { ShieldsTile } from "./tile";
import { AUTUMBRA_WATCH_FIXTURE, isUsableGhostPanel } from "./watch-fixtures";

export const dynamic = "force-dynamic";

export default async function AutumbraPage() {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  const board: ShieldBoard | null = await shieldBoard(userId).catch(() => null);
  const tile = <ShieldsTile board={board} act={shieldAction} />;
  try {
    const data = await ghostPanel(userId);
    if (!isUsableGhostPanel(data)) {
      const fixture = AUTUMBRA_WATCH_FIXTURE;
      return (
        <AutumbraConsole
          data={fixture.panel}
          threatReceipts={fixture.threatReceipts}
          look={look}
          resolve={resolve}
          tile={tile}
        />
      );
    }
    return <AutumbraConsole data={data} look={look} resolve={resolve} tile={tile} />;
  } catch {
    const fixture = AUTUMBRA_WATCH_FIXTURE;
    return (
      <AutumbraConsole
        data={fixture.panel}
        threatReceipts={fixture.threatReceipts}
        look={look}
        resolve={resolve}
        tile={tile}
      />
    );
  }
}
