import { jsonInput, InputError, routeFailure } from "@/lib/route-input";
import { NextResponse } from "next/server";
import { currentTenant } from "@/lib/tenant";
import { refuseClientImpersonation } from "@/lib/memory-session";
import { editWorkspaceMemory, forgetWorkspaceMemory } from "@/lib/workspace-gates";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ID_RE = /^[0-9a-fA-Z._:-]{1,80}$/;

/** Edit memory entry content for the signed-in tenant+user (not a permission mode). */
export async function PATCH(req: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    if (!ID_RE.test(id)) throw new InputError("Unknown memory entry.", 404);
    const body = await jsonInput(req);
    if (typeof body.text !== "string" || !body.text.trim() || body.text.length > 20000) {
      throw new InputError("Provide non-empty memory text (up to 20,000 characters).");
    }
    const { tenantId, userId } = await currentTenant();
    if (!tenantId || !userId) throw new InputError("Signed-in tenant and user required.");
    refuseClientImpersonation({ tenantId, userId }, req, body);
    const result = await editWorkspaceMemory(tenantId, userId, id, body.text.trim());
    return NextResponse.json(result);
  } catch (err) {
    return routeFailure(err);
  }
}

/** Forget one memory entry owned by the signed-in tenant+user. */
export async function DELETE(req: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    if (!ID_RE.test(id)) throw new InputError("Unknown memory entry.", 404);
    const { tenantId, userId } = await currentTenant();
    if (!tenantId || !userId) throw new InputError("Signed-in tenant and user required.");
    refuseClientImpersonation({ tenantId, userId }, req);
    const result = await forgetWorkspaceMemory(tenantId, userId, id);
    return NextResponse.json(result);
  } catch (err) {
    return routeFailure(err);
  }
}
