import { NextRequest, NextResponse } from "next/server";
import { accessRequest } from "@/lib/tank";
import { accessIdentity } from "../../identity";
const paths = new Set(["credentials", "revoke", "sites", "feeds/import", "feeds/connect", "feeds/refresh", "feeds/link"]);
export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const origin = request.headers.get("origin");
  if (!origin || origin !== request.nextUrl.origin) return NextResponse.json({ error: "Request refused." }, { status: 403 });
  const path = (await context.params).path.join("/");
  if (!paths.has(path) && !/^queue\/[0-9a-f-]{36}$/.test(path)) return NextResponse.json({ error: "Not found." }, { status: 404 });
  // Do not echo payloads, error bodies or credential values, even on bad JSON.
  try {
    const actor = await accessIdentity(request.nextUrl.searchParams.get("account"));
    const raw = await request.text();
    if (raw.length > 8_020_000) return NextResponse.json({ error: "The file is too large." }, { status: 413 });
    const result = await accessRequest(actor, path, JSON.parse(raw));
    return NextResponse.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Could not complete the request. Check the connection settings and try again. If revoking, access is denied while session removal is pending." }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if ((await context.params).path.join("/") !== "queue") return NextResponse.json({ error: "Not found." }, { status: 404 });
  try {
    const actor = await accessIdentity(null);
    return NextResponse.json(await accessRequest(actor, "queue"), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Human checks could not be loaded." }, { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
