import { SourceDocumentView } from "../../source-view";
import { notFound, redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import { marketLabRequest, type MarketDocument } from "@/lib/tank";
import "../../market-lab.css";

export const dynamic = "force-dynamic";

export default async function SourcePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ row?: string }> }) {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const { id } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) notFound();
  const query = await searchParams;
  const row = Number(query.row ?? 0);
  const offset = Number.isSafeInteger(row) && row >= 0 && row <= 10000000 ? Math.floor(row / 200) * 200 : 0;
  let source: MarketDocument;
  try {
    source = await marketLabRequest<MarketDocument>(tenant.tenantId, "document", { document_id: id, offset });
  } catch {
    return <main className="ml ml-source"><div className="ml-body"><a href="/market-lab">Back to Market Lab</a><h1>Source unavailable</h1><p>This source could not be read in your workspace. Try again shortly.</p></div></main>;
  }
  return <SourceDocumentView source={source} />;
}
