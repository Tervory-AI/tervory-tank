import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { RigClient } from "../widget/src/api/client";
import { formatPrice } from "../widget/src/api/format";
import { RigError } from "../widget/src/api/types";
import type { Price, Product, Setup } from "../widget/src/api/types";
import * as mock from "../widget/src/mock/index";
import { customNation, neutral } from "../widget/src/theme/themes";

const PRODUCT_KEYS = ["attributes", "brand", "category", "id", "image", "name", "price"];
const PRICE_KEYS = ["amount", "currency", "indicative"];
const SETUP_KEYS = ["badge", "label", "parts", "tier", "total", "why"];

function assertNoBreakdown(value: unknown): void {
  if (!value || typeof value !== "object") return;
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    expect(key.toLowerCase()).not.toMatch(/cost|duty|vat|margin|landed/);
    assertNoBreakdown(child);
  }
}

function assertPrice(price: Price): void {
  expect(Object.keys(price).sort()).toEqual(PRICE_KEYS);
  expect(price.indicative).toBe(true);
  expect(typeof price.amount).toBe("number");
  expect(typeof price.currency).toBe("string");
}

function assertProduct(product: Product, extra: string[] = []): void {
  expect(Object.keys(product).sort()).toEqual([...PRODUCT_KEYS, ...extra].sort());
  assertPrice(product.price);
  expect(product.attributes.sample).toBe(true);
  assertNoBreakdown(product);
}

function assertSetup(setup: Setup): void {
  for (const key of ["tier", "label", "parts", "total", "why"]) {
    expect(setup).toHaveProperty(key);
  }
  expect(Object.keys(setup).every((key) => SETUP_KEYS.includes(key))).toBe(true);
  assertPrice(setup.total);
  expect(setup.parts.length).toBeGreaterThan(0);
  for (const part of setup.parts) {
    expect(typeof part.role).toBe("string");
    assertProduct(part.product);
  }
  const summed = setup.parts.reduce((sum, part) => sum + part.product.price.amount, 0);
  expect(setup.total.amount).toBe(summed);
  assertNoBreakdown(setup);
}

describe("price format", () => {
  it("shows one indicative rand amount", () => {
    expect(formatPrice({ amount: 68900, currency: "ZAR", indicative: true })).toBe("R 68 900");
    expect(formatPrice({ amount: 119000, currency: "ZAR", indicative: true })).toBe("R 119 000");
    expect(formatPrice({ amount: 12.5, currency: "USD", indicative: true })).toBe("$12.50");
  });
});

describe("mock contract", () => {
  it("searches the sample catalogue", () => {
    const found = mock.search("staccato", 12);
    expect(found.results.map((item) => item.id)).toEqual(["staccato-c2", "staccato-p", "staccato-xc"]);
    found.results.forEach((item) => assertProduct(item));
    expect(mock.search("leupold").results.map((item) => item.name)).toEqual(["Leupold DeltaPoint Pro"]);
    expect(mock.search("wilson combat edc x9s").results).toEqual([]);
    expect(mock.search("staccato", 1).results).toHaveLength(1);
    expect(mock.search("").results).toEqual([]);
  });

  it("returns a product with categories that fit", () => {
    const detail = mock.product("staccato-p");
    assertProduct(detail, ["categories_that_fit"]);
    expect(detail.categories_that_fit).toEqual([
      { category: "Red dots", count: 18 },
      { category: "Holsters", count: 24 },
      { category: "Weapon lights", count: 12 },
      { category: "Magazines", count: 9 },
      { category: "Optic plates", count: 6 },
    ]);
  });

  it("returns the three Staccato P setups from the frame", () => {
    const { setups } = mock.setups("staccato-p");
    expect(setups.map((setup) => setup.tier)).toEqual(["essential", "duty", "competition"]);
    expect(setups.map((setup) => setup.label)).toEqual([
      "Everyday carry, best value",
      "Built to take a beating",
      "Fast, flat, match-ready",
    ]);
    expect(setups.map((setup) => setup.total.amount)).toEqual([87700, 96800, 91400]);
    expect(setups[1]?.badge).toBe("Most chosen");
    expect(setups[1]?.parts.map((part) => part.product.name)).toEqual([
      "Staccato P",
      "Trijicon RMR Type 2",
      "Safariland 7360RDS duty",
    ]);
    setups.forEach(assertSetup);
    expect(setups[1]?.why.split("\n")[0]).toBe("✓ Fits the Staccato P optic cut · ✓ Holster cut for this dot");
  });

  it("swaps only parts that still fit", () => {
    const duty = mock.setups("staccato-p").setups[1];
    expect(duty).toBeDefined();
    if (!duty) return;
    const dots = mock.swap(duty, "Red dot");
    expect(dots.options.map((item) => item.name).sort()).toEqual([
      "Aimpoint Acro P-2",
      "Holosun 507C X2",
      "Leupold DeltaPoint Pro",
    ]);
    dots.options.forEach((item) => assertProduct(item));
    const holsters = mock.swap(duty, "Holster");
    expect(holsters.options.map((item) => item.id)).not.toContain("safariland-7360rds");
    expect(holsters.options.length).toBeGreaterThan(0);
    expect(mock.swap(duty, "Pistol").options).toEqual([]);
    expect(mock.swap(duty, "Missing").options).toEqual([]);
  });

  it("returns the explore graph", () => {
    const graph = mock.graph("staccato-p");
    assertProduct(graph.centre);
    expect(graph.centre.id).toBe("staccato-p");
    expect(graph.branches.map((branch) => [branch.category, branch.count])).toEqual([
      ["Red dots", 18],
      ["Holsters", 24],
      ["Weapon lights", 12],
      ["Magazines", 9],
      ["Optic plates", 6],
    ]);
    const dots = graph.branches[0];
    expect(dots?.products).toHaveLength(4);
    expect(dots && dots.count - dots.products.length).toBe(14);
    graph.branches.flatMap((branch) => branch.products).forEach((item) => assertProduct(item));
  });

  it("answers only from catalogue data and cites products", () => {
    const answer = mock.ask({
      product_id: "staccato-p",
      question: "Will this fit a weapon light too?",
    });
    expect(answer.answer).toContain("12 weapon lights");
    expect(answer.answer).toContain("Streamlight TLR-1 HL");
    expect(answer.cites).toContain("staccato-p");
    expect(answer.cites).toContain("streamlight-tlr1-hl");
    expect(() => mock.ask({ product_id: "staccato-p", question: "  " })).toThrow(RigError);
  });

  it("accepts a link quote and a setup quote", () => {
    const link = mock.linkQuote({ url: "https://example.com/item", note: "Please check this" });
    expect(link.request_id).toMatch(/^req_[0-9a-f]+$/);
    const setup = mock.setups("staccato-p").setups[1];
    const quoted = mock.quote({
      setup,
      contact: { name: "Ada", email: "ada@example.com" },
    });
    expect(quoted.request_id).toMatch(/^req_[0-9a-f]+$/);
    const productQuote = mock.quote({
      product_id: "staccato-c2",
      contact: { name: "Ada", email: "ada@example.com" },
    });
    expect(productQuote.request_id).toMatch(/^req_/);
    expect(() => mock.linkQuote({ url: "not a url", note: "" })).toThrow(RigError);
    expect(() => mock.quote({ product_id: "staccato-p", contact: { name: "", email: "" } })).toThrow(RigError);
  });

  it("returns the error shape", () => {
    try {
      mock.product("missing");
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(RigError);
      const rig = error as RigError;
      expect(rig.code).toBe("not_found");
      expect(rig.message.length).toBeGreaterThan(0);
      expect(rig.status).toBe(404);
    }
  });
});

describe("API client", () => {
  it("uses the mock when api-base is mock and does not fetch", async () => {
    const fetchImpl = vi.fn();
    const client = new RigClient({ apiBase: "mock", key: "pk_demo", fetchImpl });
    const found = await client.search("staccato");
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(found.results).toHaveLength(3);
    const detail = await client.product("staccato-p");
    expect(detail.categories_that_fit.length).toBeGreaterThan(0);
    const built = await client.setups("staccato-p");
    expect(built.setups).toHaveLength(3);
    const options = await client.swap(built.setups[1] as Setup, "Red dot");
    expect(options.options.length).toBeGreaterThan(0);
    const graph = await client.graph("staccato-p");
    expect(graph.branches.length).toBe(5);
    const answer = await client.ask({ product_id: "staccato-p", question: "Which holsters fit?" });
    expect(answer.cites.length).toBeGreaterThan(0);
    const link = await client.linkQuote({ url: "https://shop.example/p", note: "sample" });
    expect(link.request_id).toMatch(/^req_/);
    const quoted = await client.quote({
      product_id: "staccato-p",
      contact: { name: "Ada", email: "ada@example.com" },
    });
    expect(quoted.request_id).toMatch(/^req_/);
  });

  it("calls every live path with the publishable key and the contract body", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ results: [], setups: [], options: [], answer: "", cites: [], request_id: "req_1", centre: {}, branches: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new RigClient({ apiBase: "https://rig.example/", key: "pk_test", fetchImpl });
    await client.search("a b", 5);
    await client.product("staccato-p");
    await client.setups("staccato-p");
    const setup = mock.setups("staccato-p").setups[1] as Setup;
    await client.swap(setup, "Red dot");
    await client.graph("staccato-p");
    await client.ask({ product_id: "staccato-p", question: "Why?", setup });
    await client.linkQuote({ url: "https://example.com", note: "note" });
    await client.quote({ product_id: "staccato-p", contact: { name: "Ada", email: "ada@example.com" } });

    const calls = fetchImpl.mock.calls as unknown as [string, RequestInit][];
    const urls = calls.map((call) => String(call[0]));
    expect(urls).toEqual([
      "https://rig.example/v1/rig/search?q=a+b&limit=5",
      "https://rig.example/v1/rig/products/staccato-p",
      "https://rig.example/v1/rig/setups",
      "https://rig.example/v1/rig/swap",
      "https://rig.example/v1/rig/graph/staccato-p",
      "https://rig.example/v1/rig/ask",
      "https://rig.example/v1/rig/link-quote",
      "https://rig.example/v1/rig/quote",
    ]);
    for (const call of calls) {
      const headers = new Headers(call[1].headers);
      expect(headers.get("X-Rig-Key")).toBe("pk_test");
    }
    const swapBody = JSON.parse(String(calls[3]?.[1].body)) as {
      setup: Setup;
      role: string;
    };
    expect(swapBody.role).toBe("Red dot");
    expect(swapBody.setup).not.toHaveProperty("badge");
    expect(swapBody.setup.total.indicative).toBe(true);
  });

  it("surfaces the error shape from a failed response", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { code: "nope", message: "No such product" } }), {
          status: 404,
        }),
    );
    const client = new RigClient({ apiBase: "https://rig.example", key: "pk_test", fetchImpl });
    await expect(client.product("missing")).rejects.toMatchObject({
      code: "nope",
      message: "No such product",
      status: 404,
    });
  });
});

describe("themes", () => {
  it("keeps retailer chrome in the theme, not a single hard-coded skin", () => {
    expect(neutral.colors.accent).not.toBe(customNation.colors.accent);
    expect(neutral.colors.canvas).not.toBe(customNation.colors.canvas);
    expect(neutral.fonts.heading).not.toBe(customNation.fonts.heading);
    expect(neutral.fonts.body).not.toBe(customNation.fonts.body);
    expect(neutral.radius).not.toBe(customNation.radius);
    expect(neutral.copy.title).not.toBe(customNation.copy.title);
    expect(neutral.copy.popular).not.toEqual(customNation.copy.popular);
    const element = readFileSync(new URL("../widget/src/element.ts", import.meta.url), "utf8");
    const render = readFileSync(new URL("../widget/src/ui/render.ts", import.meta.url), "utf8");
    expect(element).not.toMatch(/staccato|holster|pistol|9mm/i);
    expect(render).not.toMatch(/staccato|holster|pistol|9mm/i);
  });
});
