import type {
  AskRequest,
  AskResponse,
  GraphResponse,
  LinkQuoteRequest,
  Product,
  ProductDetail,
  QuoteRequest,
  RequestAck,
  SearchResponse,
  Setup,
  SetupPart,
  SetupsResponse,
  SwapResponse,
} from "../api/types";
import { RigError } from "../api/types";
import catalogueJson from "./catalogue.json";

type PartTemplate = { role: string; product_id: string };

type SetupTemplate = {
  tier: string;
  label: string;
  badge?: string;
  why: string[];
  parts: PartTemplate[];
};

type GroupTemplate = {
  category: string;
  count: number;
  product_ids: string[];
};

type Catalogue = {
  products: Product[];
  setups: Record<string, SetupTemplate[]>;
  groups: Record<string, GroupTemplate[]>;
};

const catalogue = catalogueJson as Catalogue;
const byId = new Map<string, Product>();

for (const product of catalogue.products) {
  byId.set(product.id, product);
  const price = product.price;
  if (price.indicative !== true) {
    throw new Error(`Sample price for ${product.id} must be indicative`);
  }
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function mustGet(id: string): Product {
  const product = byId.get(id);
  if (!product) throw new RigError("not_found", "That product is not in the catalogue.", 404);
  return product;
}

function hostOf(setup: Setup): Product {
  const keyed = setup.parts.map((part) => part.product).find((product) => catalogue.groups[product.id]);
  return keyed ?? setup.parts[0]?.product ?? mustGet(setup.parts[0]?.product.id ?? "");
}

function opticOf(setup: Setup): Product | undefined {
  return setup.parts.find((part) => text(part.product.attributes.footprint) !== "")?.product;
}

function holsterOf(setup: Setup): Product | undefined {
  return setup.parts.find((part) => {
    const product = part.product;
    return strings(product.attributes.fits_products).length > 0 && strings(product.attributes.fits_cuts).length > 0;
  })?.product;
}

function reprice(setup: Setup): Setup {
  const next: Setup = {
    tier: setup.tier,
    label: setup.label,
    parts: setup.parts,
    total: priceOf(setup.parts),
    why: setup.why,
  };
  if (setup.badge) next.badge = setup.badge;
  return next;
}

/**
 * Fitment uses only catalogue attributes:
 * fits_products (which hosts it mounts on) and fits_cuts (optic cut or footprint).
 * The widget never decides this; the mock does, the same way the live API will.
 */
export function fits(candidate: Product, host: Product, optic?: Product): boolean {
  const cuts = strings(candidate.attributes.fits_cuts);
  const hosts = strings(candidate.attributes.fits_products);
  const hostCut = text(host.attributes.optic_cut);
  if (hosts.length > 0 && !hosts.includes(host.id)) return false;
  if (cuts.length > 0) {
    const needed = hosts.length > 0 ? text(optic?.attributes.footprint) || hostCut : hostCut;
    if (!needed || !cuts.includes(needed)) return false;
  }
  return hosts.length > 0 || cuts.length > 0;
}

function priceOf(parts: SetupPart[]): Setup["total"] {
  const currency = parts[0]?.product.price.currency ?? "ZAR";
  const amount = parts.reduce((sum, part) => sum + part.product.price.amount, 0);
  return { amount, currency, indicative: true };
}

function materialise(template: SetupTemplate): Setup {
  const parts = template.parts.map((part) => ({
    role: part.role,
    product: mustGet(part.product_id),
  }));
  const setup: Setup = {
    tier: template.tier,
    label: template.label,
    parts,
    total: priceOf(parts),
    why: template.why,
  };
  if (template.badge) setup.badge = template.badge;
  return setup;
}

function haystack(product: Product): string {
  const bits = [product.id, product.name, product.brand, product.category, text(product.attributes.summary)];
  return bits.join(" ").toLowerCase();
}

export async function search(q: string, limit = 12): Promise<SearchResponse> {
  const query = q.trim().toLowerCase();
  const cap = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 12;
  if (!query) return { results: [] };
  const tokens = query.split(/\s+/).filter(Boolean);
  const results = catalogue.products
    .filter((product) => {
      const hay = haystack(product);
      return tokens.every((token) => hay.includes(token));
    })
    .slice(0, cap);
  return { results };
}

export async function product(id: string): Promise<ProductDetail> {
  const item = mustGet(id);
  const groups = catalogue.groups[id] ?? [];
  return {
    ...item,
    categories_that_fit: groups.map((group) => ({ category: group.category, count: group.count })),
  };
}

export async function setups(productId: string): Promise<SetupsResponse> {
  mustGet(productId);
  const templates = catalogue.setups[productId] ?? [];
  return { setups: templates.map(materialise) };
}

export async function swap(setup: Setup, role: string): Promise<SwapResponse> {
  if (!setup?.parts?.length) {
    throw new RigError("invalid_setup", "A setup is required.", 400);
  }
  const priced = reprice(setup);
  const part = priced.parts.find((item) => item.role === role);
  if (!part) return { options: [], setup: priced };
  const host = hostOf(priced);
  const optic = opticOf(priced);
  const holster = holsterOf(priced);
  const replacingOptic = text(part.product.attributes.footprint) !== "";
  const options = catalogue.products.filter((candidate) => {
    if (candidate.id === part.product.id || candidate.category !== part.product.category) return false;
    if (replacingOptic) {
      if (text(candidate.attributes.footprint) === "" || !fits(candidate, host)) return false;
      return holster ? fits(holster, host, candidate) : true;
    }
    return fits(candidate, host, optic);
  });
  return { options, setup: priced };
}

export async function graph(productId: string): Promise<GraphResponse> {
  const centre = mustGet(productId);
  const groups = catalogue.groups[productId] ?? [];
  return {
    centre,
    branches: groups.map((group) => ({
      category: group.category,
      count: group.count,
      products: group.product_ids.map((id) => mustGet(id)),
    })),
  };
}

function branchMatches(question: string, category: string): boolean {
  const q = question.toLowerCase();
  const name = category.toLowerCase();
  if (q.includes(name)) return true;
  const singular = name.endsWith("s") ? name.slice(0, -1) : name;
  return q.includes(singular);
}

export async function ask(body: AskRequest): Promise<AskResponse> {
  const question = body.question?.trim() ?? "";
  if (!question) throw new RigError("invalid_question", "Enter a question.", 400);
  const centre = mustGet(body.product_id);
  const groups = catalogue.groups[centre.id] ?? [];
  const branch = groups.find((group) => branchMatches(question, group.category));
  if (!branch) {
    const fitted = groups.map((group) => `${group.count} ${group.category.toLowerCase()}`).join(", ");
    const summary = text(centre.attributes.summary);
    return {
      answer: fitted
        ? `${centre.name}${summary ? ` (${summary})` : ""}. Fitted categories in the catalogue: ${fitted}.`
        : `${centre.name} is in the catalogue${summary ? ` (${summary})` : ""}. No fitted categories are listed for it.`,
      cites: [centre.id],
    };
  }
  const names = branch.product_ids.map((id) => mustGet(id).name);
  const listed = names.length ? `, including ${names.join(", ")}` : "";
  return {
    answer: `${branch.count} ${branch.category.toLowerCase()} fit the ${centre.name}${listed}.`,
    cites: [centre.id, ...branch.product_ids],
  };
}

function requestId(seed: string): string {
  let hash = 2166136261;
  for (const char of seed) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return `req_${(hash >>> 0).toString(16)}`;
}

export async function linkQuote(body: LinkQuoteRequest): Promise<RequestAck> {
  const url = body.url?.trim() ?? "";
  if (!/^https?:\/\//i.test(url)) {
    throw new RigError("invalid_url", "Paste a link that starts with http:// or https://.", 400);
  }
  return { request_id: requestId(`link:${url}:${body.note ?? ""}`) };
}

export async function quote(body: QuoteRequest): Promise<RequestAck> {
  const name = body.contact?.name?.trim() ?? "";
  const email = body.contact?.email?.trim() ?? "";
  if (!name || !email || !email.includes("@")) {
    throw new RigError("invalid_contact", "Name and email are required.", 400);
  }
  if (!body.setup && !body.product_id) {
    throw new RigError("invalid_quote", "A setup or product is required.", 400);
  }
  if (body.product_id) mustGet(body.product_id);
  const seed = body.setup
    ? `setup:${body.setup.tier}:${body.setup.parts.map((part) => part.product.id).join(",")}:${email}`
    : `product:${body.product_id}:${email}`;
  return { request_id: requestId(seed) };
}
