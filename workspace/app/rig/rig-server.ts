import { readFileSync } from "fs";
import path from "path";

const HOST = "https://rig.tervory.com";
const ID = /^[A-Za-z0-9._-]{1,64}$/;

type SearchHit = { id?: string; name?: string; price?: { amount?: number; currency?: string } };

function catalogueFile(): string {
  const fromWorkspace = path.resolve(process.cwd(), "../agents/rig/catalogues/customnation/publish.json");
  const fromRoot = path.resolve(process.cwd(), "agents/rig/catalogues/customnation/publish.json");
  try {
    readFileSync(fromWorkspace, "utf8");
    return fromWorkspace;
  } catch {
    return fromRoot;
  }
}

function demoKey(): string {
  const raw = JSON.parse(readFileSync(catalogueFile(), "utf8")) as { keys?: { key?: string }[] };
  const key = raw.keys?.[0]?.key;
  if (!key) throw new Error("missing");
  return key;
}

function csvCount(name: string): number {
  const file = path.join(path.dirname(catalogueFile()), name);
  const lines = readFileSync(file, "utf8").trim().split(/\r?\n/).filter(Boolean);
  return Math.max(0, lines.length - 1);
}

export function catalogueCounts(): { products: number; fits: number } {
  return { products: csvCount("products.csv"), fits: csvCount("fits.csv") };
}

export async function liveSiteUp(): Promise<boolean> {
  try {
    const response = await fetch(`${HOST}/`, { signal: AbortSignal.timeout(3000), cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

async function send(method: "GET" | "POST", pathname: string, key: string, body?: unknown): Promise<Record<string, unknown>> {
  const headers: Record<string, string> = { Accept: "application/json", "X-Rig-Key": key };
  if (body) headers["Content-Type"] = "application/json";
  const response = await fetch(`${HOST}${pathname}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(8000),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("down");
  return (await response.json()) as Record<string, unknown>;
}

function asId(value: unknown): string {
  const id = String(value ?? "");
  if (!ID.test(id)) throw new Error("bad id");
  return id;
}

function money(price: unknown): string {
  if (!price || typeof price !== "object" || !("amount" in price)) return "";
  const amount = Number((price as { amount?: number }).amount);
  if (!Number.isFinite(amount)) return "";
  return `R${Math.round(amount).toLocaleString("en-US")}`;
}

/** Read-only calls to Rig's public API. Search, graph, compare, and ask. No writes. */
export async function rigCall(op: string, payload: Record<string, unknown>): Promise<unknown> {
  const key = demoKey();
  if (op === "search") {
    const q = String(payload.q ?? "").trim().slice(0, 200);
    if (!q) return { results: [] };
    return send("GET", `/v1/rig/search?${new URLSearchParams({ q, limit: "12" })}`, key);
  }
  if (op === "graph") {
    return send("GET", `/v1/rig/graph/${encodeURIComponent(asId(payload.id))}`, key);
  }
  if (op === "compare") {
    const ids = Array.isArray(payload.product_ids) ? payload.product_ids.slice(0, 24).map(asId) : [];
    if (!ids.length) throw new Error("bad id");
    return send("POST", "/v1/rig/compare", key, { product_ids: ids });
  }
  if (op === "ask") {
    const question = String(payload.question ?? "").trim().slice(0, 500);
    if (!question) return { answer: "I don't know", items: [], sources: [] };
    const found = await send("GET", `/v1/rig/search?${new URLSearchParams({ q: question, limit: "5" })}`, key);
    const results = Array.isArray(found.results) ? (found.results as SearchHit[]) : [];
    if (!results.length || found.exact_match === false) {
      return { answer: "I don't know", items: [], sources: [] };
    }
    const productId = String(results[0]?.id ?? "");
    if (!ID.test(productId)) return { answer: "I don't know", items: [], sources: [] };
    const asked = await send("POST", "/v1/rig/ask", key, { product_id: productId, question });
    const answer = String(asked.answer ?? "I don't know");
    const cites = Array.isArray(asked.cites) ? asked.cites.map(String).filter((id) => ID.test(id)) : [];
    if (answer === "I don't know" || !cites.length) {
      return { answer: "I don't know", items: [], sources: [] };
    }
    const sources = [];
    const items = [];
    for (const id of cites) {
      let name = id;
      let price = "";
      try {
        const product = await send("GET", `/v1/rig/products/${encodeURIComponent(id)}`, key);
        name = String(product.name ?? id);
        price = money(product.price);
      } catch {
        name = id;
      }
      items.push({ name, price });
      sources.push({
        title: price ? `${name} · ${price}` : name,
        detail: `Staccato demo catalogue · product ${id} · listed in this catalogue`,
      });
    }
    return { answer, items, sources };
  }
  throw new Error("unsupported");
}
