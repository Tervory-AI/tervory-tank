/** Labels for the Tiger page. Sample rows are not shown. */

export const LEDE =
  "Watches store product pages and tells you when a price or stock changes. If a page can't be read clearly, Tiger says so instead of guessing.";
export const FOOT =
  "Public pages only. Tiger checks one page at a time, slowly, and never logs in. A store that blocks checks is recorded and skipped.";
export const FOOT_SMALL = "Tiger only lists pages you asked it to watch.";

export type ReadStatus = "Not checked" | "Read" | "Price changed" | "Stock changed" | "Can't read";

export const EVERY_OPTIONS = [
  { value: "15m", label: "Every 15 minutes" },
  { value: "1h", label: "Every hour" },
  { value: "6h", label: "Every 6 hours" },
  { value: "12h", label: "Every 12 hours" },
  { value: "1d", label: "Every day" },
] as const;
