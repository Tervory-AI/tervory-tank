import { NextResponse } from "next/server";
import { approveSkill, listSkills, retireSkill, runSkillEvals } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

// The Skala registry is platform-wide (skills are Tervory's, not a tenant's), but
// only a signed-in user may see it, and every action is recorded under their user id.
export async function GET() {
  try {
    await currentTenant();
    return NextResponse.json(await listSkills());
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => null)) as { id?: string; version?: string; action?: string } | null;
  const { id, version, action } = body ?? {};
  if (!id || !version || !action) return NextResponse.json({ error: "id, version, action required" }, { status: 400 });
  try {
    const { userId } = await currentTenant();
    if (action === "evals") return NextResponse.json(await runSkillEvals(id, version, userId));
    if (action === "approve") return NextResponse.json(await approveSkill(id, version, userId));
    if (action === "retire") return NextResponse.json(await retireSkill(id, version, userId));
    return NextResponse.json({ error: "unknown action" }, { status: 400 });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}
