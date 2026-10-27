import { NextResponse } from "next/server";
import { verifyUndoToken } from "@/lib/autumbra-undo-token";

/**
 * Owner-facing undo door. Verifies the signed email token (tenant + shield),
 * then posts a ThreatPayload undo to Autumbra Watch through Tank.
 * Public: no workspace sign-in — the token is the credential.
 */
const TANK_URL = process.env.TANK_URL ?? "http://tank:8000";
const TANK_API_KEY = process.env.TANK_API_KEY ?? "";

export async function POST(request: Request) {
  let body: { token?: string; receipt_id?: string; tenant_id?: string; site?: string; rule_id?: string };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return NextResponse.json({ ok: false, detail: "Could not read the undo request." }, { status: 400 });
  }

  const token = String(body.token || "").trim();
  let tenantId = "";
  let receiptId = "";
  let site = "";
  let ruleId = "";

  if (token) {
    try {
      const payload = verifyUndoToken(token);
      tenantId = payload.tenant_id;
      receiptId = payload.receipt_id;
      site = payload.site || "coolify.tervory.com";
      ruleId = payload.rule_id;
    } catch {
      return NextResponse.json({ ok: false, detail: "This undo link is invalid or has expired." }, { status: 401 });
    }
  } else {
    // Legacy body fields — still require tenant; prefer token from email.
    receiptId = String(body.receipt_id || "").trim();
    tenantId = String(body.tenant_id || "").trim();
    site = String(body.site || "coolify.tervory.com").trim();
    ruleId = String(body.rule_id || "").trim();
  }

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
