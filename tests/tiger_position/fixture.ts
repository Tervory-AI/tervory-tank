// Figma-only examples: this fixture is never imported by Workspace production code.
import type { TigerMatch } from "../../workspace/lib/tank";
import type { ComparisonData } from "../../workspace/app/tiger/position-model";

const at = "2026-11-03T22:00:00Z";
const match = (sku: string, name: string, site: string, path: string, state: "suggested" | "rejected", index: number): TigerMatch => ({
  id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`, tenant_id: "fixture", sku, state, method: "brand_mpn",
  url: `https://${site}-shop.example${path}`, seen_on: `https://${site}-shop.example${path}`, checked_at: at,
  site_label: site[0].toUpperCase() + site.slice(1) + " shop",
  product: { name, brand: "Fieldlight", mpn: sku },
  identifiers: { own: { brand: "Fieldlight", mpn: sku }, seen: { brand: "Fieldlight", mpn: sku, gtins: [] } },
});
export const fixture: ComparisonData = {
  positions: [
    { sku: "FL-DL01", name: "Fieldlight desk lamp", ownPrice: "£120.00", cheapest: "£100.00", rank: "3 of 3", difference: "+£20.00 · +20%",
      competitors: [
        { url: "https://north-shop.example/products/desk-lamp", label: "North shop", price: "£100.00", stock: "In stock", checkedAt: at, checked: "10 minutes ago", every: "Every hour", stale: false },
        { url: "https://west-shop.example/lights/fl-dl01", label: "West shop", price: "£110.00", stock: "In stock", checkedAt: at, checked: "20 minutes ago", every: "Every hour", stale: false },
        { url: "https://east-shop.example/fl-dl01", label: "East shop", price: "£90.00", stock: "In stock", checkedAt: at, checked: "8 hours ago", every: "Every 6 hours", stale: true },
      ] },
    { sku: "FL-WL02", name: "Fieldlight wall lamp", ownPrice: "£65.00", cheapest: "—", rank: "—", difference: "—",
      competitors: [{ url: "https://north-shop.example/products/fl-wl02", label: "North shop", price: null, stock: null, checkedAt: null, checked: null, every: null, stale: false }] },
    { sku: "FL-SH03", name: "Fieldlight shade", ownPrice: "£40.00", cheapest: "—", rank: "—", difference: "—", competitors: [] },
  ],
  matches: [match("FL-DL01", "Fieldlight desk lamp", "north", "/products/desk-lamp", "suggested", 1), match("FL-WL02", "Fieldlight wall lamp", "east", "/products/wall-lamp", "rejected", 2)],
  sites: [
    { id: "north", label: "North shop", url: "https://north-shop.example", host: "north-shop.example", pages: 84, matches: 26, checkedAt: at, checked: "10 minutes ago", status: "checked", skipped: null },
    { id: "west", label: "West shop", url: "https://west-shop.example", host: "west-shop.example", pages: 12, matches: 3, checkedAt: at, checked: "25 minutes ago", status: "human_check", skipped: null },
    { id: "east", label: "East shop", url: "https://east-shop.example", host: "east-shop.example", pages: 18, matches: 5, checkedAt: at, checked: "1 hour ago", status: "robots", skipped: 7 },
  ],
  plugins: null,
};
fixture.plugins = { enabled: true, message: null, secrets: [], files: [], connections: [], links: (fixture.sites ?? []).map(row => ({
  id: row.id, url: row.url, label: row.label, frequency: "daily", lastChecked: row.checkedAt, status: row.status ?? "not_checked",
})) };
