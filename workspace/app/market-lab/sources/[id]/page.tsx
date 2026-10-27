import { StoredSourcePage } from "../../source-page";
import { redirect } from "next/navigation";
import { activeTenant } from "@/lib/tenant";
import "../../market-lab.css";

export const dynamic = "force-dynamic";

export default async function SourcePage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ row?: string }> }) {
  const tenant = await activeTenant();
  if (!tenant) redirect("/onboarding");
  const { id } = await params;
  const { row } = await searchParams;
  return <StoredSourcePage tenantId={tenant.tenantId} id={id} row={row} />;
}
