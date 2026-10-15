import { NextResponse } from "next/server";
import { baseBatches } from "@/lib/tank";
import { activeTenant } from "@/lib/tenant";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// New organizations have no batches yet, so the home page sends them here.
// A missing organization also needs onboarding. If Tank is down, leave the home page alone.
export async function GET() {
  try {
    const tenant = await activeTenant();
    if (!tenant) return NextResponse.json({ needs: true });
    const batches = await baseBatches(tenant.tenantId);
    return NextResponse.json({ needs: batches.length === 0 });
  } catch {
    return NextResponse.json({ needs: false });
  }
}
