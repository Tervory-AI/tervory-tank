import { jsonInput, InputError, routeFailure } from "@/lib/route-input";
import { NextResponse } from "next/server";
import { currentTenant } from "@/lib/tenant";
import { refuseClientImpersonation } from "@/lib/memory-session";
import {
  setWorkspaceMemoryControl,
  viewWorkspaceMemory,
  type MemoryControl,
} from "@/lib/workspace-gates";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const CONTROLS = new Set(["off", "view", "edit", "forget"]);

/** Signed-in view of the caller's own memories (scoped to currentTenant). */
export async function GET(req: Request) {
  try {
    const { tenantId, userId } = await currentTenant();
    if (!tenantId || !userId) throw new InputError("Signed-in tenant and user required.");
    refuseClientImpersonation({ tenantId, userId }, req);
    const url = new URL(req.url);
    const taskKey = url.searchParams.get("task_key") || "memory_control";
    const memoryId = url.searchParams.get("memory_id") || undefined;
    const result = await viewWorkspaceMemory(tenantId, userId, taskKey, memoryId);
    return NextResponse.json(result);
  } catch (err) {
    return routeFailure(err);
  }
}

/** Set per-tenant+user memory_control: off | view | edit | forget. */
export async function POST(req: Request) {
  try {
    const body = await jsonInput(req);
    const control = body.control;
    if (typeof control !== "string" || !CONTROLS.has(control)) {
      throw new InputError("Choose memory control off, view, edit, or forget.");
    }
    const { tenantId, userId } = await currentTenant();
    if (!tenantId || !userId) throw new InputError("Signed-in tenant and user required.");
    refuseClientImpersonation({ tenantId, userId }, req, body);
    const result = await setWorkspaceMemoryControl(tenantId, userId, control as MemoryControl);
    return NextResponse.json(result);
  } catch (err) {
    return routeFailure(err);
  }
}
