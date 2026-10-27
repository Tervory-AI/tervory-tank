import { createHmac, timingSafeEqual } from "crypto";

export type UndoTokenPayload = {
  tenant_id: string;
  receipt_id: string;
  rule_id: string;
  site: string;
  exp: number;
};

function secret(): string {
  const raw =
    (process.env.AUTUMBRA_UNDO_TOKEN_SECRET || "").trim() ||
    (process.env.AUTUMBRA_EDGE_WEBHOOK_SECRET || "").trim();
  if (!raw) throw new Error("AUTUMBRA_UNDO_TOKEN_SECRET is not configured.");
  return raw;
}

function b64url(buf: Buffer): string {
  return buf.toString("base64url");
}

function b64urlDecode(text: string): Buffer {
  return Buffer.from(text, "base64url");
}

/** Verify a signed, expiring undo token. Throws on failure. */
export function verifyUndoToken(token: string, nowSec = Math.floor(Date.now() / 1000)): UndoTokenPayload {
  const raw = (token || "").trim();
  const dot = raw.indexOf(".");
  if (dot <= 0) throw new Error("undo token missing");
  const body = raw.slice(0, dot);
  const sig = raw.slice(dot + 1);
  if (!body || !sig) throw new Error("undo token malformed");
  const expected = b64url(createHmac("sha256", secret()).update(body).digest());
  const a = Buffer.from(expected);
  const b = Buffer.from(sig);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new Error("undo token signature invalid");
  }
  const payload = JSON.parse(b64urlDecode(body).toString("utf8")) as UndoTokenPayload;
  if (!payload || typeof payload !== "object") throw new Error("undo token payload invalid");
  if (!payload.exp || Number(payload.exp) < nowSec) throw new Error("undo token expired");
  const tenant_id = String(payload.tenant_id || "").trim();
  const receipt_id = String(payload.receipt_id || "").trim();
  if (!tenant_id || !receipt_id) throw new Error("undo token missing tenant or receipt");
  return {
    tenant_id,
    receipt_id,
    rule_id: String(payload.rule_id || "").trim(),
    site: String(payload.site || "").trim(),
    exp: Number(payload.exp),
  };
}
