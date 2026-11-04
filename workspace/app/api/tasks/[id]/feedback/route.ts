import { NextResponse } from "next/server";
import { currentTenant } from "@/lib/tenant";
import { taskFeedback } from "@/lib/tank";

export const runtime = "nodejs";

export async function POST(req: Request, context: {params: Promise<{id: string}>}) {
  const body = await req.json().catch(() => null) as {feedback?: unknown; note?: unknown} | null;
  if (!body || (body.feedback !== "accepted" && body.feedback !== "wrong") ||
      (body.note !== undefined && typeof body.note !== "string") ||
      (typeof body.note === "string" && body.note.length > 1000) ||
      (body.feedback === "wrong" && !(typeof body.note === "string" && body.note.trim()))) {
    return NextResponse.json({error:"Choose a verdict and explain what was wrong."}, {status:400});
  }
  try {
    const identity = await currentTenant();
    const {id} = await context.params;
    const response = await taskFeedback(identity, id, body.feedback as "accepted" | "wrong", body.note as string | undefined);
    return NextResponse.json(await response.json(), {status:response.status, headers:{"cache-control":"private, no-store"}});
  } catch {
    return NextResponse.json({error:"The feedback could not be saved."}, {status:502});
  }
}
