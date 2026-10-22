export type FitReview = { part_sku: string; part_name: string; fits_sku: string | null; fits_family: string | null; fits_with: string; note: string; confidence: number | null; rule?: Record<string, unknown> };
export type FeedReceipt = { id: string; provider: string; site: string; added: number; updated: number; rejected: number; created_at: string };
export type RetailerPanel = {
  price_configured: boolean; currency: string; products: number; can_set_exchange_rate: boolean;
  feeds: { provider: string; site: string; next_refresh: string | null }[];
  templates: Record<string, Record<string, string>>;
  fits: FitReview[]; missed_searches: { query: string; count: number }[]; receipts: FeedReceipt[];
};
export type AdminResult = { ok: boolean; message: string; panel?: RetailerPanel };
export type AdminOperation = "connect" | "import" | "refresh" | "price-rule" | "exchange-rate" | "templates" | "approve" | "reject" | "suggest";
