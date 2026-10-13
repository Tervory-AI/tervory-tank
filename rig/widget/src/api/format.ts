import type { Price, Product } from "./types";

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

export function whyLines(why: readonly string[]): string[] {
  return why.map((line) => line.trim()).filter(Boolean);
}
