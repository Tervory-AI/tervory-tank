export type BatchStatus = "held" | "pooled" | "rejected" | "removed";

export type QuarantineBatch = {
  id: string;
  seriesId: string;
  source: string;
  region: string;
  currency: string;
  unit: string;
  fetchedAt: string;
  status: BatchStatus;
  reason: string;
};

const STATUSES: BatchStatus[] = ["held", "pooled", "rejected", "removed"];

export function quarantineActions(status: BatchStatus): Array<"Release" | "Reject" | "Remove"> {
  if (status === "held") return ["Release", "Reject"];
  if (status === "pooled") return ["Remove"];
  return [];
}

export function nextStatus(status: BatchStatus, action: "release" | "reject" | "remove"): BatchStatus | null {
  if (action === "release" && status === "held") return "pooled";
  if (action === "reject" && status === "held") return "rejected";
  if (action === "remove" && (status === "held" || status === "pooled")) return "removed";
  return null;
}

export function entersPool(status: BatchStatus): boolean {
  return status === "pooled";
}

export function asBatch(row: Record<string, unknown>): QuarantineBatch | null {
  const status = String(row.status ?? "");
  if (!STATUSES.includes(status as BatchStatus)) return null;
  const id = String(row.id ?? "").trim();
  if (!id) return null;
  return {
    id,
    seriesId: String(row.series_id ?? row.seriesId ?? ""),
    source: String(row.source ?? ""),
    region: String(row.region ?? ""),
    currency: String(row.currency ?? ""),
    unit: String(row.unit ?? ""),
    fetchedAt: String(row.fetched_at ?? row.fetchedAt ?? ""),
    status: status as BatchStatus,
    reason: String(row.reason ?? ""),
  };
}
