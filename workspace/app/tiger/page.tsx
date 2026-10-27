import { activeTenant } from "@/lib/tenant";
import { oneParam } from "../prices/format";
import { loadTiger } from "./load";
import { sectionFrom } from "./model";
import { TigerApp } from "./view";

export const dynamic = "force-dynamic";

export default async function TigerPage({
  searchParams,
}: {
  searchParams: Promise<{ notice?: string | string[]; tab?: string | string[] }>;
}) {
  const params = await searchParams;
  const loaded = await loadTiger();
  let accountName: string | null = null;
  try {
    accountName = (await activeTenant())?.orgName ?? null;
  } catch {
    accountName = null;
  }
  const notice = oneParam(params.notice) || loaded.notice || "";
  return (
    <TigerApp
      data={loaded.data}
      notice={notice}
      initialTab={sectionFrom(oneParam(params.tab))}
      accountName={accountName}
    />
  );
}
