import type { Price, Product, SetupPart } from "./types";

export function formatPrice(price: Price): string {
  const digits = Number.isInteger(price.amount) ? 0 : 2;
  const [whole, frac] = price.amount.toFixed(digits).split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const amount = frac ? `${grouped}.${frac}` : grouped;
  if (price.currency === "ZAR") return `R ${amount}`;
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: price.currency,
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(price.amount);
  } catch {
    return `${price.currency} ${amount}`;
  }
}

/** One indicative total from item prices the API already sent. */
export function indicativeTotal(parts: SetupPart[], fallback: Price): Price {
  if (parts.length === 0) return fallback;
  const currency = parts[0].product.price.currency;
  if (!parts.every((part) => part.product.price.currency === currency)) return fallback;
  const amount = parts.reduce((sum, part) => sum + part.product.price.amount, 0);
  return {
    amount: Math.round(amount * 100) / 100,
    currency,
    indicative: true,
  };
}

export function isSample(product: Product): boolean {
  return product.attributes.sample === true;
}

export function summaryOf(product: Product): string {
  return typeof product.attributes.summary === "string" ? product.attributes.summary : product.category;
}

export function detailOf(product: Product): string {
  return typeof product.attributes.detail === "string" ? product.attributes.detail : summaryOf(product);
}

export function matchNote(product: Product): string {
  return typeof product.attributes.match_note === "string" ? product.attributes.match_note : "";
}

export function whyLines(why: string): string[] {
  return why
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}
