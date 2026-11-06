import { jsonInput, InputError, routeFailure } from "@/lib/route-input";
import { NextResponse } from "next/server";
import { route, type ChatMessage } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

// One request in, one answer out. Tank decides the model and writes the ledger row.
export async function POST(req: Request) {
  try {
    const body = await jsonInput(req);
    if (!Array.isArray(body.messages) || !body.messages.length || body.messages.length > 12 || body.messages.some(m => !m || !["user", "assistant"].includes(m.role) || typeof m.content !== "string" || !m.content.trim() || m.content.length > 20000)) throw new InputError("Add up to 12 user or assistant messages, each under 20,000 characters.");
    const messages = body.messages as ChatMessage[];
    const { tenantId } = await currentTenant();
    const result = await route(tenantId, "tier0.answer", messages.slice(-12));
    return NextResponse.json(result);
  } catch (err) {
    return routeFailure(err);
  }
}
