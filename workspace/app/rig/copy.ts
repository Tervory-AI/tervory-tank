/** Approved copy from the Rig agent frames. Example labels stay on Plugins only. */

export const MASK = "•••• saved 17 Oct";
export const REFRESHED = "Today, 7:30 AM PT · Example";

export const TABS = [
  { id: "search", label: "Search" },
  { id: "overview", label: "Overview" },
  { id: "catalogues", label: "Catalogues" },
  { id: "fits", label: "Fits to review" },
  { id: "skins", label: "Skins" },
  { id: "progress", label: "Progress" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export type Part = {
  id: string;
  type: string;
  name: string;
  price: number;
  market: number | null;
};

export type Pistol = {
  id: string;
  name: string;
  price: number;
  market: number | null;
};

export const PISTOLS: Pistol[] = [
  { id: "STI-C2-9", name: "Staccato C2", price: 58999, market: 59000 },
  { id: "STI-P-9", name: "Staccato P", price: 64999, market: 65000 },
  { id: "STI-XC-9", name: "Staccato XC", price: 89999, market: 90000 },
];

/** Parts the Staccato C2 frame shows, in that order. Prices match the demo catalogue. */
export const C2_PARTS: Part[] = [
  { id: "HOL-507C-X2", type: "Optics", name: "Holosun 507C X2", price: 5499, market: 5500 },
  { id: "TRIJ-RMR-T2", type: "Optics", name: "Trijicon RMR Type 2", price: 9999, market: 10000 },
  { id: "DAW-FO-FRONT", type: "Sights", name: "Dawson fiber front sight", price: 899, market: 900 },
  { id: "TEN8-REAR", type: "Sights", name: "10-8 rear sight", price: 1299, market: null },
  { id: "CHEELY-C2", type: "Grips", name: "Cheely compact grip", price: 3299, market: 3300 },
  { id: "ATLAS-FLAT", type: "Triggers", name: "Atlas flat trigger", price: 2199, market: 2200 },
  { id: "TENICOR-VELO", type: "Holsters", name: "Tenicor Velo holster", price: 2199, market: 2200 },
  { id: "SF-X300U", type: "Lights", name: "SureFire X300U", price: 4999, market: 5000 },
  { id: "MAG-16", type: "Magazines", name: "2011 magazine 16 round", price: 1199, market: 1200 },
];

export const SEED_ADDED = ["HOL-507C-X2", "SF-X300U"];

export const BUILT = [
  { title: "Search the catalogue", text: "Type a brand or model, like Staccato, and get the matching products." },
  {
    title: "Compatible upgrades",
    text: "Each pistol shows parts that fit, sorted by type: optics, sights, grips, triggers, holsters, lights, magazines.",
  },
  {
    title: "Prices",
    text: "Every part shows the retailer's price. The market average shows once the selection is final.",
  },
  {
    title: "Fit approval",
    text: "New fits wait on the Fits to review tab until an admin approves them with the admin key.",
  },
  {
    title: "Honest answers",
    text: "A model we don't stock says “No exact match” and shows the closest ones. Rig never makes one up.",
  },
] as const;

export const PLAN = [
  {
    code: "R4",
    title: "Search and compatible upgrades",
    text: "Search the catalogue, see the parts that fit each pistol with retailer prices, market average once the selection is final, fit approval with the admin key.",
    state: "Done",
    on: true,
  },
  {
    code: "R5",
    title: "3D models",
    text: "A simple 3D model of each pistol and part. Fit comes from maker standards like the RMSc optic footprint, so they don't have to be perfect.",
    state: "Next",
    on: false,
  },
  {
    code: "R6",
    title: "3D builder",
    text: "The shopper's whole build shown in 3D, live in front of them, with the best prices beside it.",
    state: "Later",
    on: false,
  },
  {
    code: "—",
    title: "Dealer skins",
    text: "Custom Nation first, after the main product is done.",
    state: "Later",
    on: false,
  },
] as const;

export const CHANGES = [
  { id: "94", title: "Homepage searches the Staccato demo", when: "Live 3:57 PM PT" },
  { id: "93", title: "Fixed the startup crash", when: "Earlier" },
  { id: "90", title: "Search and compatible upgrades (R4)", when: "Earlier" },
] as const;

export const SKIN_STEPS = [
  "Same search and fits as the main Rig.",
  "The dealer's own logo, colours and prices.",
  "Tervory's name and logo never show on the dealer's page.",
  "Built only after the main product is done.",
] as const;

export type WaitingFit = {
  id: string;
  name: string;
  fits: string;
  why: string;
};

export const WAITING: WaitingFit[] = [
  {
    id: "tenicor-p",
    name: "Tenicor Velo holster",
    fits: "fits Staccato P",
    why: "The maker lists a version cut for full-size 2011 pistols.",
  },
  {
    id: "mag-17-c2",
    name: "2011 magazine 17 round",
    fits: "fits Staccato C2",
    why: "Same 2011 magazine. It fits, but sticks out past the shorter grip.",
  },
];

export const DECIDED = [
  {
    id: "holosun-p",
    name: "Holosun 507C X2",
    fits: "fits Staccato P",
    why: "Same optic footprint as the maker lists for this pistol.",
    state: "Approved",
    on: true,
  },
  {
    id: "cheely-c2",
    name: "Cheely E2 grip",
    fits: "fits Staccato C2",
    why: "Full-size grip. The C2 has a shorter frame.",
    state: "Rejected",
    on: false,
  },
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
  { name: "supplier-price-list-oct.csv", type: "CSV", size: "1,240 rows", when: "16 Oct", status: "Processed", on: true, map: true },
  { name: "dealer-inventory.xlsx", type: "XLSX", size: "3,880 rows", when: "15 Oct", status: "Needs checking", on: false, map: false },
  { name: "state-rules-summary.pdf", type: "PDF", size: "42 pages", when: "12 Oct", status: "Processed", on: true, map: false },
  { name: "freight-rates-q3.csv", type: "CSV", size: "610 rows", when: "10 Oct", status: "Needs checking", on: false, map: true },
] as const;

export const LINKS = [
  { label: "Texas hunting seasons", host: "tpwd.texas.gov", checked: "Today, 7:00 AM", status: "Watching", on: true },
  { label: "UPS hazardous goods rules", host: "ups.com", checked: "Yesterday", status: "Changed", on: false },
  { label: "Port of Long Beach stats", host: "polb.com", checked: "16 Oct", status: "Couldn't reach", on: false },
] as const;

export const CONNECTIONS = [
  { name: "Supplier catalogue", host: "catalog.example-supplier.com", detail: "Product prices and stock levels", status: "Connected", on: true, used: "Today, 7:10 AM" },
  { name: "Shipping rates", host: "mcp.example-freight.com", detail: "Carrier rates by route", status: "Needs sign-in", on: false, used: "Never" },
  { name: "News monitor", host: "news.example-mcp.org", detail: "Headlines that mention your market", status: "Error", on: false, used: "14 Oct" },
] as const;

export type PluginTab = "keys" | "files" | "links" | "mcp";

export const PLUGIN_TABS: { id: PluginTab; label: string }[] = [
  { id: "keys", label: "API keys" },
  { id: "files", label: "Files" },
  { id: "links", label: "Source links" },
  { id: "mcp", label: "MCP connections" },
];

export const OPENING_QUESTION = "What optics fit the Staccato C2?";

export const OPENING_ANSWER = "Two optics in the catalogue are approved to fit the Staccato C2:";

export const OPENING_ITEMS = [
  { name: "Holosun 507C X2", price: "R5,499" },
  { name: "Trijicon RMR Type 2", price: "R9,999" },
];

export const OPENING_SOURCES = [
  {
    title: "Holosun 507C X2 · R5,499",
    detail: "Staccato demo catalogue · product HOL-507C-X2 · approved fit for Staccato 2011 pistols",
  },
  {
    title: "Trijicon RMR Type 2 · R9,999",
    detail: "Staccato demo catalogue · product TRIJ-RMR-T2 · approved fit for Staccato 2011 pistols",
  },
  {
    title: "Staccato C2",
    detail: "Staccato demo catalogue · product STI-C2-9 · part of the Staccato 2011 range",
  },
];
