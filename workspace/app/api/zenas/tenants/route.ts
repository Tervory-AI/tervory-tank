import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { NextResponse } from "next/server";
import { isFounder } from "@/lib/admin";
import { chosenHome, statedReason } from "../rules";
import { zenas } from "../tank";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const { userId } = await auth();
  if (!isFounder(userId)) notFound();
  const body = (await req.json().catch(() => null)) as { tenant_id?: unknown; home_region?: unknown } | null;
  const tenantId = typeof body?.tenant_id === "string" ? body.tenant_id.trim() : "";
  const home = chosenHome(body?.home_region);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tenantId) || !home) {
    return NextResponse.json({ error: "Choose za or us-east." }, { status: 400 });
  }
  try {
    const res = await zenas("tenants", {
      method: "POST",
      body: JSON.stringify({ tenant_id: tenantId, home_region: home }),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok || (payload && typeof payload === "object" && (payload as { ok?: unknown }).ok === false)) {
      const reason = statedReason(payload) ?? "The home region was not set.";
      const status = res.status === 403 ? 403 : res.ok ? 422 : 502;
      return NextResponse.json({ error: reason }, { status });
    }
    const created = Boolean(payload && typeof payload === "object" && (payload as { created?: unknown }).created === true);
    return NextResponse.json({ ok: true, created, home_region: home, tenant_id: tenantId }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "The home region was not set.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
