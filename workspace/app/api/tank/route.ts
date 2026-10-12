import { NextResponse } from "next/server";
import { evalsSummary, ladder, promoteCandidate, rollbackModel, setCandidate } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

// The ladder is platform-wide (Tervory's routing policy), visible to signed-in users; actions carry the user id.
export async function GET() {
  try {
    await currentTenant();
    const [rows, evals] = await Promise.all([ladder(), evalsSummary()]);
    return NextResponse.json({ ladder: rows, evals });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { task_type?: string; action?: string; candidate_model?: string | null; shadow_rate?: number } | null;
  if (!body?.task_type || !body.action) return NextResponse.json({ error: "task_type and action required" }, { status: 400 });
  try {
    const { userId } = await currentTenant();
    if (body.action === "candidate") return NextResponse.json(await setCandidate(body.task_type, body.candidate_model ?? null, body.shadow_rate ?? 1, userId));
    if (body.action === "promote") return NextResponse.json(await promoteCandidate(body.task_type, userId));
    if (body.action === "rollback") return NextResponse.json(await rollbackModel(body.task_type, userId));
    return NextResponse.json({ error: "unknown action" }, { status: 400 });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}
