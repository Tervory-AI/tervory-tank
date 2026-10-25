import { listTigerAlerts, listTigerObservations, listTigerWatches } from "@/lib/tank";
import { activeTenant } from "@/lib/tenant";
import { emptyData, fromTiger, type TigerData } from "./model";

export type TigerLoad = { data: TigerData; notice: string | null };

/**
 * Reads watches, observations and alerts from Tank.
 * Signed-out / no active org → honest empty lists (not invented sample watches).
 * Read only: nothing is queued or saved here.
 */
export async function loadTiger(): Promise<TigerLoad> {
  const tenant = await activeTenant();
  if (!tenant) return { data: emptyData(), notice: null };
  try {
    const [listed, alerted] = await Promise.all([
      listTigerWatches(tenant.tenantId),
      listTigerAlerts(tenant.tenantId),
    ]);
    const watches = Array.isArray(listed.watches) ? listed.watches : [];
    const alerts = Array.isArray(alerted.alerts) ? alerted.alerts : [];
    if (watches.length === 0 && alerts.length === 0) return { data: emptyData(), notice: null };
    const batches = await Promise.all(
      watches.slice(0, 40).map(async (watch) => {
        try {
          const data = await listTigerObservations(tenant.tenantId, watch.url);
          return Array.isArray(data.observations) ? data.observations : [];
        } catch {
          return [];
        }
      }),
    );
    return { data: fromTiger(watches, batches.flat(), alerts), notice: null };
  } catch {
    return { data: emptyData(), notice: "Tiger is not reachable right now. No products are shown." };
  }
}
