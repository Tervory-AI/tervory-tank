import { NextResponse } from "next/server";
import { currentTenant } from "@/lib/tenant";
import { taskBoard } from "@/lib/tank";

export const runtime = "nodejs";

export async function GET() {
  try {
    const response = await taskBoard(await currentTenant());
    return NextResponse.json(await response.json(), {status:response.status, headers:{"cache-control":"private, no-store"}});
  } catch {
    return NextResponse.json({error:"The task board is unavailable."}, {status:502});
  }
}
