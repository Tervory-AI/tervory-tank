import { jsonInput, InputError, routeFailure } from "@/lib/route-input";
import { submitOnce } from "@/lib/submission";
import { NextResponse } from "next/server";
import { createTask, listTasks, type ChatMessage } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

const ALLOWED_TASK_TYPES = new Set(["tier0.answer", "tier0.draft", "reason.brief"]);

// GET: the board for the signed-in tenant.
export async function GET() {
  try {
    const { tenantId } = await currentTenant();
    return NextResponse.json(await listTasks(tenantId, 50));
  } catch (err) {
    return routeFailure(err);
  }
}

// POST: queue a task. Tank runs it and the board picks up the result.
export async function POST(req: Request) {
  try {
    const body = await jsonInput(req);
    if (typeof body.title !== "string" || !body.title.trim() || body.title.length > 200 ||
        typeof body.request !== "string" || !body.request.trim() || body.request.length > 20000) throw new InputError("Add a title and what you need done (up to 20,000 characters).");
    const title = body.title.trim(), request = body.request.trim();
    const taskType = body.task_type ?? "tier0.answer";
    if (typeof taskType !== "string" || !ALLOWED_TASK_TYPES.has(taskType)) throw new InputError("Choose an available task kind.");
    const { tenantId, userId } = await currentTenant();
    const messages: ChatMessage[] = [{ role: "user", content: request }];
    const result = await submitOnce(tenantId, userId, req.headers.get("Idempotency-Key"), { title, taskType, messages }, () => createTask(tenantId, userId, title, taskType, messages));
    return NextResponse.json(result, { status: 202 });
  } catch (err) {
    return routeFailure(err);
  }
}
