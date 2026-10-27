import { NextResponse } from "next/server";

/**
 * Owner-facing undo door. Posts a ThreatPayload undo to Autumbra Watch through Tank.
 * Public page button hits this; secrets stay server-side.
 */
const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export async function POST(request: Request) {
  let body: { receipt_id?: string; tenant_id?: string; site?: string; rule_id?: string };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ ok: false, detail: "Could not read the undo request." }, { status: 400 });
  }
  const receiptId = String(body.receipt_id || "").trim();
  const tenantId = String(body.tenant_id || "").trim();
  const site = String(body.site || "coolify.tervory.com").trim();
  const ruleId = String(body.rule_id || "").trim();
  if (!receiptId && !ruleId) {
    return NextResponse.json({ ok: false, detail: "Missing receipt to undo." }, { status: 400 });
  }
  if (!tenantId) {
    return NextResponse.json({ ok: false, detail: "Missing client id." }, { status: 400 });
  }
  if (!TANK_API_KEY) {
    return NextResponse.json(
      { ok: false, detail: "Undo is not configured on this host yet." },
      { status: 503 },
    );
  }
  // Tank admin corridor → Watch queue/undo (ThreatPayload door).
  const payload = {
    tenant_id: tenantId,
    site,
    prior_receipt_id: receiptId || undefined,
    rule_id: ruleId || undefined,
  };
  try {
    const res = await fetch(`${TANK_URL}/v1/ghost/autumbra/queue/undo`, {
      method: "POST",
      cache: "no-store",
      headers: {
        "content-type": "application/json",
        "x-tank-key": TANK_API_KEY,
      },
      body: JSON.stringify(payload),
    });
    const text = await res.text();
    let data: unknown = null;
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text.slice(0, 200) };
    }
    if (!res.ok) {
      return NextResponse.json(
        { ok: false, detail: "Could not undo that shield right now.", upstream: data },
        { status: res.status >= 500 ? 502 : res.status },
      );
    }
    return NextResponse.json({ ok: true, queued: true, result: data });
  } catch {
    return NextResponse.json(
      { ok: false, detail: "Could not reach Autumbra to undo." },
      { status: 502 },
    );
  }
}
