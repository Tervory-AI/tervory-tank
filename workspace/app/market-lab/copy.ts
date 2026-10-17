/** Approved example copy from Market Lab — App. Placeholders stay placeholders. */

export const MASK = "•••• saved 17 Oct";
export const REFRESHED = "Today, 7:30 AM PT · Example";

export const ON_FEEDS = [
  {
    title: "Severe-weather alerts",
    detail: "Active storm, flood and heat warnings that can slow shipping or close stores.",
    value: "412",
    unit: "active alerts",
    meta: "Every 15 min · Updated 7:30 AM · National Weather Service",
  },
  {
    title: "Monthly licence listings",
    detail: "Federal firearms licences listed this month, a read on how many sellers are active.",
    value: "78,410",
    unit: "licences listed",
    meta: "Monthly · Updated 1 Oct · ATF",
  },
  {
    title: "Background-check counts",
    detail: "Checks run at the point of sale, a close stand-in for demand.",
    value: "2.1M",
    unit: "checks last month",
    meta: "Monthly · Updated 3 Oct · FBI NICS",
  },
  {
    title: "Federal Register notices",
    detail: "New federal rules and notices that touch your market.",
    value: "34",
    unit: "notices this week",
    meta: "Daily · Updated 6:00 AM · Federal Register",
  },
  {
    title: "Federal hazmat shipping rules",
    detail: "Changes to the rules for moving hazardous goods.",
    value: "2 Oct",
    unit: "last change",
    meta: "Daily · Updated 6:00 AM · eCFR",
  },
  {
    title: "World commodity prices",
    detail: "Prices for oil, metals and grain that feed into your costs.",
    value: "$78.20",
    unit: "crude oil, per barrel",
    meta: "Monthly · Updated 2 Oct · World Bank",
  },
  {
    title: "Freight moved index",
    detail: "How much freight moved across the country compared with normal.",
    value: "138.4",
    unit: "index points",
    meta: "Monthly · Updated 9 Oct · BTS",
  },
  {
    title: "Port of Los Angeles container volume",
    detail: "Containers through the busiest US port, an early sign of imports.",
    value: "812K",
    unit: "containers, Sept.",
    meta: "Monthly · Updated 14 Oct · Port of Los Angeles",
  },
  {
    title: "Licence holders by state",
    detail: "Where licence holders are, so you can see which states are growing.",
    value: "50 + DC",
    unit: "states covered",
    meta: "Yearly · Updated 1 Jul · State licence records",
  },
] as const;

export const OFF_FEEDS = [
  { title: "FRED economic series", env: "FRED_API_KEY" },
  { title: "Census population", env: "CENSUS_API_KEY" },
  { title: "Census trade", env: "CENSUS_API_KEY" },
  { title: "EIA on-highway diesel", env: "EIA_API_KEY" },
  { title: "Monthly climate", env: "NOAA_TOKEN" },
  { title: "State bill tracking", env: "LEGISCAN_API_KEY" },
] as const;

export const LINKED = [
  { title: "Carrier rules", detail: "What each carrier allows you to ship, and where." },
  { title: "State pages", detail: "One page per state with its own feeds and rules." },
  { title: "Hunting seasons", detail: "Season dates by state, so you can plan stock ahead." },
  { title: "Other ports", detail: "Container volume at Long Beach, Savannah and more." },
] as const;

export type KeyId = "fred" | "census" | "eia" | "noaa" | "legiscan";

export const KEYS: { id: KeyId; name: string; detail: string; env: string; saved: boolean }[] = [
  { id: "fred", name: "FRED", detail: "Seven economic series: interest rates, jobs, prices", env: "FRED_API_KEY", saved: true },
  { id: "census", name: "Census", detail: "Census population and Census trade", env: "CENSUS_API_KEY", saved: true },
  { id: "eia", name: "EIA", detail: "On-highway diesel prices", env: "EIA_API_KEY", saved: false },
  { id: "noaa", name: "NOAA", detail: "Monthly climate", env: "NOAA_TOKEN", saved: false },
  { id: "legiscan", name: "LegiScan", detail: "State bill tracking", env: "LEGISCAN_API_KEY", saved: false },
];

export const FILES = [
  { name: "supplier-price-list-oct.csv", type: "CSV", size: "1,240 rows", when: "16 Oct", status: "Processed", map: true },
  { name: "dealer-inventory.xlsx", type: "XLSX", size: "3,880 rows", when: "15 Oct", status: "Needs checking", map: false },
  { name: "state-rules-summary.pdf", type: "PDF", size: "42 pages", when: "12 Oct", status: "Processed", map: false },
  { name: "freight-rates-q3.csv", type: "CSV", size: "610 rows", when: "10 Oct", status: "Needs checking", map: true },
] as const;

export const LINKS = [
  { label: "Texas hunting seasons", host: "tpwd.texas.gov", checked: "Today, 7:00 AM", status: "Watching" },
  { label: "UPS hazardous goods rules", host: "ups.com", checked: "Yesterday", status: "Changed" },
  { label: "Port of Long Beach stats", host: "polb.com", checked: "16 Oct", status: "Couldn't reach" },
] as const;

export const CONNECTIONS = [
  { name: "Supplier catalogue", host: "catalog.example-supplier.com", detail: "Product prices and stock levels", status: "Connected", used: "Today, 7:10 AM" },
  { name: "Shipping rates", host: "mcp.example-freight.com", detail: "Carrier rates by route", status: "Needs sign-in", used: "Never" },
  { name: "News monitor", host: "news.example-mcp.org", detail: "Headlines that mention your market", status: "Error", used: "14 Oct" },
] as const;

export type SourceTab = "keys" | "files" | "links" | "mcp";

export const TABS: { id: SourceTab; label: string }[] = [
  { id: "keys", label: "API keys" },
  { id: "files", label: "Files" },
  { id: "links", label: "Source links" },
  { id: "mcp", label: "MCP connections" },
];
