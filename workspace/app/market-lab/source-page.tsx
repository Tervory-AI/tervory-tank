import { notFound } from "next/navigation";
import { marketLabRequest, MarketLabRequestError, type MarketDocument } from "@/lib/tank";
import { SourceDocumentView } from "./source-view";

/** Same source load and error path for the authenticated page and local proof. */
export async function StoredSourcePage({ tenantId, id, row }: { tenantId: string; id: string; row?: string }) {
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) notFound();
  const requestedRow = Number(row ?? 0);
  const offset = Number.isSafeInteger(requestedRow) && requestedRow >= 0 && requestedRow <= 10000000 ? Math.floor(requestedRow / 200) * 200 : 0;
  let source: MarketDocument;
  try {
    source = await marketLabRequest<MarketDocument>(tenantId, "document", { document_id: id, offset });
  } catch (error) {
    if (error instanceof MarketLabRequestError && error.status === 404) notFound();
    return <main className="ml ml-source"><div className="ml-body"><a href="/market-lab">Back to Market Lab</a><h1>Source unavailable</h1><p>This source could not be read in your workspace. Try again shortly.</p></div></main>;
  }
  return <SourceDocumentView source={source} />;
}
