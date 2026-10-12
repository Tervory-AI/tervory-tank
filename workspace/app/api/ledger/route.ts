import { NextResponse } from "next/server";
import { ledgerSummary } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

export async function GET(req: Request) {
  const days = Number(new URL(req.url).searchParams.get("days") ?? "30") || 30;
  try {
    const { tenantId } = await currentTenant();
    return NextResponse.json(await ledgerSummary(tenantId, days));
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : "Tank unavailable" }, { status: 502 });
  }
}
