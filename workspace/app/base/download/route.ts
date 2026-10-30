import { currentTenant } from "@/lib/tenant";

export const runtime = "nodejs";

// Keep saved batch links working through the same per-field export as the counts.
export async function GET(request: Request): Promise<Response> {
  try { await currentTenant(); }
  catch { return new Response("Sign in to download your results.", { status: 401 }); }
  const batch = new URL(request.url).searchParams.get("batch")?.trim();
  if (!batch || batch.length > 120) return new Response("Choose a batch from your list.", { status: 400 });
  const destination = new URL("/base/product/records.csv", request.url);
  destination.search = new URLSearchParams({ batch, metric: "attempted", include_collectors: "true" }).toString();
  return Response.redirect(destination, 307);
}
