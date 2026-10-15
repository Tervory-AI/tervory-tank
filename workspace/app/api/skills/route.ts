import { NextResponse } from "next/server";
import { approveSkill, listSkills, retireSkill, runSkillEvals, trySkill } from "@/lib/tank";
import { rejectUnlessFounder } from "@/app/review/access";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

// Skills belong to Tervory. A founder may list them and approve or retire a version.
async function deny(): Promise<NextResponse | null> {
  const denied = await rejectUnlessFounder();
  if (!denied) return null;
  return NextResponse.json({ error: denied.error }, { status: denied.status });
}

export async function GET() {
  const denied = await deny();
  if (denied) return denied;
  try {
    await currentTenant();
    return NextResponse.json(await listSkills());
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}

export async function POST(req: Request) {
  const denied = await deny();
  if (denied) return denied;
  const body = (await req.json().catch(() => null)) as { id?: string; version?: string; action?: string; input?: Record<string, unknown> } | null;
  const { id, version, action } = body ?? {};
  if (!id || !version || !action) return NextResponse.json({ error: "id, version, action required" }, { status: 400 });
  try {
    const { userId, tenantId } = await currentTenant();
    if (action === "try") {
      if (!body?.input || typeof body.input !== "object") return NextResponse.json({ error: "input required" }, { status: 400 });
      return NextResponse.json(await trySkill(tenantId, id, version, body.input));
    }
    if (action === "evals") return NextResponse.json(await runSkillEvals(id, version, userId));
    if (action === "approve") return NextResponse.json(await approveSkill(id, version, userId));
    if (action === "retire") return NextResponse.json(await retireSkill(id, version, userId));
    return NextResponse.json({ error: "unknown action" }, { status: 400 });
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}
