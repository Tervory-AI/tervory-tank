import { auth } from "@clerk/nextjs/server";
import { isFounder } from "@/lib/admin";
import { runContextTrial } from "@/lib/tank";
import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) return new Response(null, { status: 404 });
  if (request.headers.get("origin") !== new URL(request.url).origin) {
    return new Response(null, { status: 403 });
  }
  try {
    return NextResponse.json(await runContextTrial(userId));
  } catch {
    return NextResponse.json({ error: "Trial interrupted. Refresh results before trying again." }, { status: 503 });
  }
}
