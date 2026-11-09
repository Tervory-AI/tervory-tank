/**
 * What the Rig overview says, worked out only from this account's Rig room counts.
 * A section with nothing real to show is replaced by one line saying what will appear
 * there and what is needed. Nothing here is example or demo data.
 */

export type RigStatus = {
  /** Every catalogue row; null when Rig did not answer. */
  products: number | null;
  /** Approved fits: what shoppers see. */
  fits: number | null;
  /** Rows shoppers can find in search (not marked inactive). */
  active: number | null;
  /** Suggested fits waiting for an admin. */
  waiting: number | null;
  /** Scheduled catalogue feeds. */
  feeds: number | null;
  /** A quote delivery email or webhook is saved. */
  delivery: boolean | null;
};

export type BuiltRow = { title: string; text: string };
export type NextStep = { title: string; text: string; href: string; link: string };

export const ADMIN = "/rig/admin";

function plural(count: number, one: string, many: string): string {
  return `${count.toLocaleString("en-US")} ${count === 1 ? one : many}`;
}

export function statusFrom(products: number | null, fits: number | null, more?: Partial<RigStatus> | null): RigStatus {
  return {
    products,
    fits,
    active: more?.active ?? null,
    waiting: more?.waiting ?? null,
    feeds: more?.feeds ?? null,
    delivery: more?.delivery ?? null,
  };
}

/** Searchable rows, and the line saying why the rest are hidden. */
export function searchableLine(status: RigStatus): string | null {
  const { products, active } = status;
  if (products === null || products === 0 || active === null) return null;
  if (active === products) return `All ${plural(products, "product shows", "products show")} in search.`;
  const hidden = products - active;
  return `${plural(active, "product shows", "products show")} in search. ${plural(hidden, "product is", "products are")} marked inactive in the catalogue, so shoppers don't see ${hidden === 1 ? "it" : "them"}.`;
}

/** What is really set up for this account, from its own Rig room. */
export function builtRows(status: RigStatus): BuiltRow[] {
  const rows: BuiltRow[] = [];
  const { products, fits, feeds, delivery } = status;
  if (products !== null && products > 0) {
    rows.push({ title: "Catalogue", text: `${plural(products, "product", "products")} imported. ${searchableLine(status) ?? ""}`.trim() });
  }
  if (fits !== null && fits > 0) {
    rows.push({ title: "Approved fits", text: `${plural(fits, "fit is", "fits are")} approved. Shoppers see them as compatible upgrades.` });
  }
  if (feeds !== null && feeds > 0) {
    rows.push({ title: "Catalogue feed", text: `${plural(feeds, "feed refreshes", "feeds refresh")} the catalogue every night.` });
  }
  if (delivery === true) {
    rows.push({ title: "Quote delivery", text: "Shoppers' quote requests go to the store's saved email or webhook." });
  }
  return rows;
}

/** The line shown in place of an empty "What's built". */
export function builtEmptyLine(status: RigStatus): string {
  if (status.products === null) {
    return "Rig did not answer for this account, so what's built can't be shown. Reload the page to try again.";
  }
  return "Nothing is set up for this account yet. This list shows the catalogue, approved fits, feeds and quote delivery as each one is set up.";
}

/** The real next step for this account, first missing piece first. Null when nothing is waiting. */
export function nextStep(status: RigStatus): NextStep | null {
  const { products, fits, active, waiting, delivery } = status;
  if (products === null) return null;
  if (products === 0) {
    return { title: "Import your catalogue", text: "Upload your catalogue file or connect an official feed. Search, fits and answers all start from it.", href: ADMIN, link: "Open Rig admin" };
  }
  if (active === 0) {
    return { title: "Make products searchable", text: `All ${plural(products, "product is", "products are")} marked inactive, so search shows nothing. Mark the ones you sell as active and import the file again.`, href: ADMIN, link: "Open Rig admin" };
  }
  if (waiting !== null && waiting > 0) {
    return { title: `Review ${plural(waiting, "suggested fit", "suggested fits")}`, text: "Approve or reject each one. Shoppers only see approved fits.", href: ADMIN, link: "Open the fit approval queue" };
  }
  if (fits === 0) {
    return { title: "Find fit suggestions", text: "Rig suggests parts that fit each product. Nothing reaches shoppers until you approve it.", href: ADMIN, link: "Open Rig admin" };
  }
  if (delivery === false) {
    return { title: "Set where quote requests go", text: "Save the store's email or webhook so shoppers' quote requests reach you.", href: ADMIN, link: "Open Rig admin" };
  }
  return null;
}

/** The line shown in place of an empty "Next step". */
export function nextEmptyLine(status: RigStatus): string {
  if (status.products === null) {
    return "Rig did not answer for this account, so the next step can't be shown. Reload the page to try again.";
  }
  return "Nothing is waiting. The catalogue, approved fits and quote delivery are set up.";
}

/** What "Ask Rig" can answer. Every answer comes from this catalogue's products and approved fits. */
export function askTopics(product: string | null): string[] {
  const subject = product ? product : "a product";
  return [
    `Which parts fit ${subject}`,
    `Whether one part fits ${subject}`,
    `What ${subject} costs in this catalogue`,
  ];
}
