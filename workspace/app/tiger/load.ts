import { listTigerAlerts, listTigerObservations, listTigerWatches } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";
import { exampleData, fromTiger, type TigerData } from "./model";

export type TigerLoad = { data: TigerData; notice: string | null };

export async function loadTiger(): Promise<TigerLoad> {
  try {
    const tenant = await currentTenant();
    const [listed, alerted] = await Promise.all([
      listTigerWatches(tenant.tenantId),
      listTigerAlerts(tenant.tenantId),
    ]);
    const watches = Array.isArray(listed.watches) ? listed.watches : [];
    const alerts = Array.isArray(alerted.alerts) ? alerted.alerts : [];
    if (watches.length === 0 && alerts.length === 0) return { data: exampleData(), notice: null };
    const batches = await Promise.all(watches.slice(0, 40).map(async (watch) => {
      try {
        const data = await listTigerObservations(tenant.tenantId, watch.url);
        return Array.isArray(data.observations) ? data.observations : [];
      } catch {
        return [];
      }
    }));
    return { data: fromTiger(watches, batches.flat(), alerts), notice: null };
  } catch (err) {
    const text = err instanceof Error ? err.message : "";
    if (text.includes("not signed in")) return { data: exampleData(), notice: null };
    return { data: exampleData(), notice: "Tiger is not reachable right now. The rows below are an Example." };
  }
}
