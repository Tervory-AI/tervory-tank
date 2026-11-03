import { commandRequest } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";
import { workspaceOrigin } from "@/lib/workspace-origin";

export const runtime = "nodejs";

// Keep saved batch links working through the same per-field export as the counts.
export async function GET(request: Request): Promise<Response> {
  let tenant;
  try { tenant = await currentTenant(); }
  catch { return new Response("Sign in to download your results.", { status: 401 }); }
  const listId = new URL(request.url).searchParams.get("list_id");
  if (listId !== null) {
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(listId)) return new Response(null, { status: 400 });
    const upstream = await commandRequest(tenant, `base/lists/csv?${new URLSearchParams({ list_id: listId })}`);
    return new Response(upstream.body, { headers: { "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="base-list.csv"', "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
  }
  const batch = new URL(request.url).searchParams.get("batch")?.trim();
  if (!batch || batch.length > 120) return new Response("Choose a batch from your list.", { status: 400 });
  const origin = workspaceOrigin(request);
  if (!origin) return new Response("Open this download in your workspace.", { status: 400 });
  const destination = new URL("/base/product/records.csv", origin);
  destination.search = new URLSearchParams({ batch, metric: "attempted", include_collectors: "true" }).toString();
  return Response.redirect(destination, 307);
}
