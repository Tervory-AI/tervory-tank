/** Example rows from the Tiger app frames. Placeholders stay labelled Example. */

export const REFRESHED = "Today, 7:30 AM PT · Example";
export const LEDE =
  "Watches store product pages and tells you when a price or stock changes. If a page can't be read clearly, Tiger says so instead of guessing.";
export const FOOT =
  "Public pages only. Tiger checks one page at a time, slowly, and never logs in. A store that blocks checks is recorded and skipped.";
export const FOOT_SMALL = "Values marked Example are placeholders in this design.";

export type ReadStatus = "Read" | "Price changed" | "Stock changed" | "Can't read";

export type ExampleProduct = {
  id: string;
  name: string;
  store: string;
  path: string;
  price: string;
  stock: string;
  checked: string;
  status: ReadStatus;
  every: string;
  alertOn: string;
};

export const PRODUCTS: ExampleProduct[] = [
  { id: "ex-shoe", name: "Trail running shoe", store: "store-a.example", path: "store-a.example/trail-shoe", price: "$88.00", stock: "In stock", checked: "7:30 AM", status: "Read", every: "Every 6 hours", alertOn: "Price and stock" },
  { id: "ex-bottle", name: "Ceramic water bottle", store: "store-b.example", path: "store-b.example/bottle-750", price: "$17.48", stock: "In stock", checked: "7:30 AM", status: "Price changed", every: "Every 6 hours", alertOn: "Price and stock" },
  { id: "ex-earbuds", name: "Wireless earbuds", store: "store-c.example", path: "store-c.example/earbuds-pro", price: "$39.98", stock: "Out of stock", checked: "7:28 AM", status: "Stock changed", every: "Every 12 hours", alertOn: "Stock only" },
  { id: "ex-cream", name: "Face cream, 50 ml", store: "store-d.example", path: "store-d.example/face-cream", price: "—", stock: "—", checked: "7:26 AM", status: "Can't read", every: "Every day", alertOn: "Price and stock" },
  { id: "ex-pods", name: "Laundry pods, 42 pack", store: "store-a.example", path: "store-a.example/pods-42", price: "$16.98", stock: "Only 3 left", checked: "7:25 AM", status: "Read", every: "Every day", alertOn: "Price only" },
  { id: "ex-jacket", name: "Kids rain jacket", store: "store-e.example", path: "store-e.example/rain-jacket", price: "—", stock: "—", checked: "7:22 AM", status: "Can't read", every: "Every day", alertOn: "Price and stock" },
];

export type ExampleRead = { id: string; when: string; product: string; price: string; stock: string };

export const READS: ExampleRead[] = [
  { id: "rd-earbuds-now", when: "Today, 7:28 AM", product: "Wireless earbuds", price: "$39.98", stock: "Out of stock" },
  { id: "rd-earbuds-then", when: "14 Oct, 9:00 AM", product: "Wireless earbuds", price: "$44.98", stock: "In stock" },
  { id: "rd-shoe", when: "Today, 7:30 AM", product: "Trail running shoe", price: "$88.00", stock: "In stock" },
  { id: "rd-bottle", when: "Today, 7:30 AM", product: "Ceramic water bottle", price: "$17.48", stock: "In stock" },
  { id: "rd-pods", when: "Today, 7:25 AM", product: "Laundry pods, 42 pack", price: "$16.98", stock: "Only 3 left" },
];

export type ExampleAlert = {
  id: string;
  when: string;
  product: string;
  store: string;
  kind: "Price" | "Stock";
  before: string;
  now: string;
  change: string;
  today: boolean;
};

export const ALERTS: ExampleAlert[] = [
  { id: "al-bottle", when: "Today, 7:30 AM", product: "Ceramic water bottle", store: "store-b.example", kind: "Price", before: "$19.99", now: "$17.48", change: "Price went down from $19.99 to $17.48", today: true },
  { id: "al-earbuds-stock", when: "Today, 7:28 AM", product: "Wireless earbuds", store: "store-c.example", kind: "Stock", before: "In stock", now: "Out of stock", change: "Now out of stock. Was in stock.", today: true },
  { id: "al-pods", when: "Today, 6:10 AM", product: "Laundry pods, 42 pack", store: "store-a.example", kind: "Stock", before: "In stock", now: "Only 3 left", change: "Stock is low: only 3 left", today: true },
  { id: "al-shoe", when: "Yesterday, 4:15 PM", product: "Trail running shoe", store: "store-a.example", kind: "Price", before: "$78.00", now: "$88.00", change: "Price went up from $78.00 to $88.00", today: false },
  { id: "al-jacket", when: "Yesterday, 9:02 AM", product: "Kids rain jacket", store: "store-e.example", kind: "Stock", before: "Out of stock", now: "In stock", change: "Back in stock. Was out of stock.", today: false },
  { id: "al-earbuds-price", when: "14 Oct, 11:40 AM", product: "Wireless earbuds", store: "store-c.example", kind: "Price", before: "$44.98", now: "$39.98", change: "Price went down from $44.98 to $39.98", today: false },
];

export type ExampleUnread = { id: string; product: string; store: string; why: string; since: string };

export const UNREAD: ExampleUnread[] = [
  { id: "un-cream", product: "Face cream, 50 ml", store: "store-d.example", why: "A sale price and a higher price are shown for the same product.", since: "Today, 7:26 AM" },
  { id: "un-jacket", product: "Kids rain jacket", store: "store-e.example", why: "The page layout changed, so the price could not be found.", since: "Today, 7:22 AM" },
  { id: "un-lamp", product: "Desk lamp", store: "store-f.example", why: "Stock wording was not clear: “selling fast”.", since: "Yesterday" },
  { id: "un-hose", product: "Garden hose, 15 m", store: "store-g.example", why: "The store blocked automatic checks. Recorded and skipped.", since: "15 Oct" },
];

export type AskTurn =
  | { who: "You"; text: string }
  | { who: "Tiger"; text: string; sources: string[] };

export const ASK: AskTurn[] = [
  { who: "You", text: "Which watched products changed price this week, and is anything out of stock?" },
  {
    who: "Tiger",
    text: "Two products changed price this week. The ceramic water bottle went down from $19.99 to $17.48. The trail running shoe went up from $78.00 to $88.00. The wireless earbuds have been out of stock since 7:28 AM today. I couldn’t read the face cream page, so I haven’t guessed its price.",
    sources: [
      "store-b.example product page, read 7:30 AM",
      "store-a.example product page, read 7:30 AM",
      "store-c.example product page, read 7:28 AM",
      "store-d.example product page, can’t read at 7:26 AM",
    ],
  },
  { who: "You", text: "Watch the kids rain jacket every 6 hours." },
  {
    who: "Tiger",
    text: "Done. I’ll check the kids rain jacket every 6 hours and alert you when its price or stock changes. Right now the page can’t be read because the layout changed, so there is no price yet.",
    sources: ["store-e.example product page, can’t read at 7:22 AM"],
  },
];

export const EVERY_OPTIONS = [
  { value: "15m", label: "Every 15 minutes" },
  { value: "1h", label: "Every hour" },
  { value: "6h", label: "Every 6 hours" },
  { value: "12h", label: "Every 12 hours" },
  { value: "1d", label: "Every day" },
] as const;
