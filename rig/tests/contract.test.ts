import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import { RigClient } from "../widget/src/api/client";
import { formatPrice } from "../widget/src/api/format";
import { RigError } from "../widget/src/api/types";
import type { Price, Product, Setup } from "../widget/src/api/types";
import * as mock from "../widget/src/mock/index";
import { customNation, neutral, resolveTheme } from "../widget/src/theme/themes";

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
  expect(Array.isArray(setup.why)).toBe(true);
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
  it("searches the sample catalogue", async () => {
    const found = await mock.search("staccato", 12);
    expect(found.results.map((item) => item.id)).toEqual(["staccato-c2", "staccato-p", "staccato-xc"]);
    found.results.forEach((item) => assertProduct(item));
    expect((await mock.search("leupold")).results.map((item) => item.name)).toEqual(["Leupold DeltaPoint Pro"]);
    expect((await mock.search("leupold")).results[0]?.attributes.footprint).toBe("DPP");
    expect((await mock.search("aimpoint")).results[0]?.attributes.footprint).toBe("ACRO");
    expect((await mock.search("wilson combat edc x9s")).results).toEqual([]);
    expect((await mock.search("staccato", 1)).results).toHaveLength(1);
    expect((await mock.search("")).results).toEqual([]);
  });

  it("returns a product with categories that fit", async () => {
    const detail = await mock.product("staccato-p");
    assertProduct(detail, ["categories_that_fit"]);
    expect(detail.categories_that_fit).toEqual([
      { category: "Red dots", count: 18 },
      { category: "Holsters", count: 24 },
      { category: "Weapon lights", count: 12 },
      { category: "Magazines", count: 9 },
      { category: "Optic plates", count: 6 },
    ]);
  });

  it("returns the three Staccato P setups from the frame", async () => {
    const { setups } = await mock.setups("staccato-p");
    expect(setups.map((setup) => setup.tier)).toEqual(["essential", "duty", "competition"]);
    expect(setups.map((setup) => setup.label)).toEqual([
      "Everyday carry, best value",
      "Built to take a beating",
      "Fast, flat, match-ready",
    ]);
    expect(setups.map((setup) => setup.total.amount)).toEqual([87700, 96800, 89000]);
    expect(setups[1]?.badge).toBe("Most chosen");
    expect(setups[1]?.parts.map((part) => part.product.name)).toEqual([
      "Staccato P",
      "Trijicon RMR Type 2",
      "Safariland 7360RDS duty",
    ]);
    setups.forEach(assertSetup);
    expect(setups[1]?.why[0]).toBe("✓ Fits the Staccato P optic cut · ✓ Holster cut for this dot");
    expect(setups[1]?.why.join(" ")).not.toMatch(/matching plate/i);
  });

  it("swaps only parts that still fit and returns the server total", async () => {
    const duty = (await mock.setups("staccato-p")).setups[1];
    expect(duty).toBeDefined();
    if (!duty) return;
    const dots = await mock.swap(duty, "Red dot");
    expect(dots.options.map((item) => item.name)).toEqual(["Holosun 507C X2"]);
    expect(dots.options.map((item) => item.id)).not.toContain("leupold-deltapoint-pro");
    expect(dots.options.map((item) => item.id)).not.toContain("aimpoint-acro-p2");
    expect(dots.setup.total.amount).toBe(96800);
    dots.options.forEach((item) => assertProduct(item));
    const holosun = dots.options[0];
    expect(holosun).toBeDefined();
    if (!holosun) return;
    const next = {
      ...duty,
      parts: duty.parts.map((part) => (part.role === "Red dot" ? { role: part.role, product: holosun } : part)),
    };
    const priced = await mock.swap(next, "Red dot");
    expect(priced.setup.total.amount).toBe(90200);
    expect(priced.setup.parts.find((part) => part.role === "Red dot")?.product.id).toBe("holosun-507c");
    const holsters = await mock.swap(duty, "Holster");
    expect(holsters.options.map((item) => item.id)).not.toContain("safariland-7360rds");
    expect(holsters.options.length).toBeGreaterThan(0);
    expect((await mock.swap(duty, "Pistol")).options).toEqual([]);
    expect((await mock.swap(duty, "Missing")).options).toEqual([]);
  });

  it("returns the explore graph", async () => {
    const graph = await mock.graph("staccato-p");
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
    expect(dots?.products).toHaveLength(2);
    expect(dots && dots.count - dots.products.length).toBe(16);
    graph.branches.flatMap((branch) => branch.products).forEach((item) => assertProduct(item));
  });

  it("answers only from catalogue data and cites products", async () => {
    const answer = await mock.ask({
      product_id: "staccato-p",
      question: "Will this fit a weapon light too?",
    });
    expect(answer.answer).toContain("12 weapon lights");
    expect(answer.answer).toContain("Streamlight TLR-1 HL");
    expect(answer.cites).toContain("staccato-p");
    expect(answer.cites).toContain("streamlight-tlr1-hl");
    await expect(mock.ask({ product_id: "staccato-p", question: "  " })).rejects.toThrow(RigError);
  });

  it("accepts a link quote and a setup quote", async () => {
    const link = await mock.linkQuote({ url: "https://example.com/item", note: "Please check this" });
    expect(link.request_id).toMatch(/^req_[0-9a-f]+$/);
    const setup = (await mock.setups("staccato-p")).setups[1];
    const quoted = await mock.quote({
      setup,
      contact: { name: "Ada", email: "ada@example.com" },
    });
    expect(quoted.request_id).toMatch(/^req_[0-9a-f]+$/);
    const productQuote = await mock.quote({
      product_id: "staccato-c2",
      contact: { name: "Ada", email: "ada@example.com" },
    });
    expect(productQuote.request_id).toMatch(/^req_/);
    await expect(mock.linkQuote({ url: "not a url", note: "" })).rejects.toThrow(RigError);
    await expect(mock.quote({ product_id: "staccato-p", contact: { name: "", email: "" } })).rejects.toThrow(RigError);
  });

  it("returns the error shape", async () => {
    try {
      await mock.product("missing");
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
    const setup = (await mock.setups("staccato-p")).setups[1] as Setup;
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
    expect(resolveTheme(null).id).toBe("neutral");
    expect(resolveTheme("custom-nation").id).toBe("custom-nation");
    const element = readFileSync(new URL("../widget/src/element.ts", import.meta.url), "utf8");
    const render = readFileSync(new URL("../widget/src/ui/render.ts", import.meta.url), "utf8");
    const client = readFileSync(new URL("../widget/src/api/client.ts", import.meta.url), "utf8");
    expect(element).not.toMatch(/staccato|holster|pistol|9mm/i);
    expect(element).not.toMatch(/indicativeTotal/);
    expect(render).not.toMatch(/staccato|holster|pistol|9mm/i);
    expect(client).not.toMatch(/from ["']\.\.\/mock/);
    expect(new RigClient({ apiBase: "", key: "pk_demo" }).usesMock).toBe(false);
    expect(new RigClient({ apiBase: "mock", key: "pk_demo" }).usesMock).toBe(true);
  });
});
