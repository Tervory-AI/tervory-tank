import { NextResponse } from "next/server";
import { currentTenant } from "@/lib/tenant";
import { requireReviewer } from "@/app/review/access";
import { homeRegion, zenas } from "../tank";
import { presentReview } from "../rules";

export const runtime = "nodejs";

export async function GET() {
  const reviewer = await requireReviewer();
  try {
    const { tenantId } = await currentTenant();
    const home = homeRegion();
    const tags = reviewer.jurisdictions.join(",");
    const res = await zenas(`review?tenant_id=${tenantId}&home_region=${home}&jurisdiction=${tags}`, { method: "GET" });
    if (res.status === 404) {
      return NextResponse.json({ items: [], note: "The review queue is not on this server yet." });
    }
    if (!res.ok) return NextResponse.json({ error: "The review queue could not be loaded." }, { status: 502 });
    const payload = await res.json();
    return NextResponse.json({ items: presentReview(payload, reviewer.jurisdictions) });
  } catch (err) {
    const message = err instanceof Error ? err.message : "The review queue could not be loaded.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
