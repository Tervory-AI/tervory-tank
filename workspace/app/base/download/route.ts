import { currentTenant } from "@/lib/tenant";
import { readBatch, verifiedCsv } from "../batch-data";

export const runtime = "nodejs";

export async function GET(request: Request): Promise<Response> {
  let tenant;
  try { tenant = await currentTenant(); }
  catch { return new Response("Sign in to download your results.", { status: 401 }); }
  const batch = new URL(request.url).searchParams.get("batch")?.trim();
  if (!batch || batch.length > 120) return new Response("Choose a batch from your list.", { status: 400 });
  try {
    const rows = await readBatch(tenant.tenantId, batch);
    if (!rows.length) return new Response("Batch not found in your workspace.", { status: 404 });
    if (rows.some((row) => row.status === "pending")) return new Response("This list is still being checked.", { status: 409 });
    if (!rows.some((row) => row.status === "verified")) return new Response("No rows have a verified source and check date. Review the reasons on Base.", { status: 409 });
    return new Response(verifiedCsv(rows), { headers: {
      "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": 'attachment; filename="verified-businesses.csv"',
      "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch { return new Response("The download could not be completed. Please try again.", { status: 503 }); }
}
