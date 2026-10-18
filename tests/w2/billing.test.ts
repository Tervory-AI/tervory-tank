import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  COPY,
  checkoutHref,
  checkoutNotice,
  createCheckoutUrl,
  emptyBilling,
  formatMoney,
  invoiceHref,
  loadBilling,
  majorUnits,
  originFromHeaders,
  planPriceIds,
  plansFromPrices,
  readInvoices,
  readPrice,
  resolveOrigin,
  safeOrigin,
  type FetchLike,
} from "../../workspace/app/billing/billing.ts";

const KEY = "sk_test_billingfixture";
const TENANT = "7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b";

function json(body: unknown, status = 200): { ok: boolean; status: number; json: () => Promise<unknown> } {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

test("amounts come from the unit Stripe sends, and a missing amount stays a dash", () => {
  assert.equal(formatMoney(2500, "usd"), "$25.00");
  assert.equal(formatMoney(0, "usd"), "$0.00");
  assert.equal(formatMoney(null, "usd"), COPY.dash);
  assert.equal(formatMoney(2500, null), COPY.dash);
  assert.equal(formatMoney(Number.NaN, "usd"), COPY.dash);
  assert.equal(majorUnits(1500, "jpy"), 1500);
  assert.equal(formatMoney(1500, "jpy"), new Intl.NumberFormat("en-US", { style: "currency", currency: "JPY" }).format(1500));
  assert.equal(majorUnits(1000, "kwd"), 1);
  assert.equal(formatMoney(1000, "kwd").includes("10.00"), false);
});

test("price ids are a list the founder sets, and anything else is ignored", () => {
  assert.deepEqual(planPriceIds(undefined), []);
  assert.deepEqual(planPriceIds("  price_fixture , price_other,price_fixture "), ["price_fixture", "price_other"]);
  assert.deepEqual(planPriceIds("sk_test_billingfixture, price_ok, not-a-price, price_bad/../x"), ["price_ok"]);
});

test("invoice and checkout links stay on Stripe", () => {
  assert.equal(invoiceHref("https://invoice.stripe.com/i/acct_fixture/test"), "https://invoice.stripe.com/i/acct_fixture/test");
  assert.equal(invoiceHref("https://pay.stripe.com/invoice/test"), "https://pay.stripe.com/invoice/test");
  assert.equal(invoiceHref("http://invoice.stripe.com/i/test"), null);
  assert.equal(invoiceHref("https://evil.example/invoice.stripe.com"), null);
  assert.equal(invoiceHref("javascript:alert(1)"), null);
  assert.equal(checkoutHref("https://checkout.stripe.com/c/pay/cs_test_fixture"), "https://checkout.stripe.com/c/pay/cs_test_fixture");
  assert.equal(checkoutHref("https://checkout.stripe.com.evil.example/c/pay"), null);
  assert.equal(checkoutHref("https://evil.example/checkout"), null);
});

test("return origin is an origin only", () => {
  assert.equal(safeOrigin("https://app.tervory.com"), "https://app.tervory.com");
  assert.equal(safeOrigin("https://app.tervory.com/billing"), null);
  assert.equal(safeOrigin("https://user:pass@app.tervory.com"), null);
  assert.equal(originFromHeaders("https", "app.tervory.com"), "https://app.tervory.com");
  assert.equal(originFromHeaders("http", "localhost:3000"), "http://localhost:3000");
  assert.equal(originFromHeaders("https", "evil.com\napp.tervory.com"), null);
  assert.equal(resolveOrigin("https://app.tervory.com", "http", "localhost:3000"), "https://app.tervory.com");
  assert.equal(resolveOrigin("", "https", "app.tervory.com"), "https://app.tervory.com");
});

test("a price with no unit amount does not invent one", () => {
  const price = readPrice({
    id: "price_fixture",
    unit_amount: null,
    currency: "usd",
    recurring: { interval: "month", interval_count: 1, usage_type: "licensed" },
    product: { name: "Field", description: "" },
  });
  assert.ok(price);
  const [plan] = plansFromPrices(price ? [price] : [], null);
  assert.equal(plan.amount, COPY.dash);
  assert.equal(plan.caption, COPY.amountPending);
  assert.equal(plan.name, "Field");
  assert.equal(plan.description, null);
});

test("invoices keep Stripe's amount and drop a link that is not Stripe's", () => {
  const rows = readInvoices({
    data: [
      {
        number: null,
        status: "open",
        total: 500,
        currency: "usd",
        created: 1760000000,
        hosted_invoice_url: "https://billing.example/steal",
      },
    ],
  });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].number, COPY.dash);
  assert.equal(rows[0].status, "Open");
  assert.equal(rows[0].amount, "$5.00");
  assert.equal(rows[0].href, null);
  assert.equal(rows[0].paid, false);
});

test("without a secret, billing does not call Stripe and does not invent a price", async () => {
  let called = false;
  const fetchImpl: FetchLike = async () => {
    called = true;
    throw new Error("network");
  };
  const view = await loadBilling(TENANT, { fetch: fetchImpl, env: { STRIPE_SECRET_KEY: "  ", STRIPE_PLAN_PRICE_IDS: "price_fixture" } });
  assert.equal(called, false);
  assert.deepEqual(view, emptyBilling(true));
  assert.equal(view.plans.length, 0);
});

test("a configured plan, usage, and invoice are read from Stripe responses", async () => {
  const calls: { url: string; authorization: string }[] = [];
  const fetchImpl: FetchLike = async (url, init) => {
    calls.push({ url, authorization: init?.headers?.Authorization ?? "" });
    if (url.includes("/prices/")) {
      return json({
        id: "price_fixture",
        unit_amount: 2500,
        currency: "usd",
        recurring: { interval: "month", interval_count: 1, usage_type: "licensed" },
        product: { name: "Field", description: "For a shop floor." },
      });
    }
    if (url.includes("/customers/search")) return json({ data: [{ id: "cus_fixture" }] });
    if (url.includes("/subscriptions")) {
      return json({ data: [{ status: "active", items: { data: [{ price: { id: "price_fixture" } }] } }] });
    }
    if (url.includes("/invoices/upcoming")) {
      return json({
        amount_due: 2500,
        currency: "usd",
        period_start: 1760000000,
        period_end: 1762592000,
        lines: { data: [{ description: "Seats", quantity: 2, amount: 2500, currency: "usd" }] },
      });
    }
    if (url.includes("/invoices?")) {
      return json({
        data: [{
          number: "A-1",
          status: "paid",
          total: 2500,
          currency: "usd",
          created: 1760000000,
          hosted_invoice_url: "https://invoice.stripe.com/i/acct_fixture/test",
        }],
      });
    }
    return json(null, 500);
  };
  const view = await loadBilling(TENANT, {
    fetch: fetchImpl,
    env: { STRIPE_SECRET_KEY: KEY, STRIPE_PLAN_PRICE_IDS: "price_fixture" },
  });
  assert.equal(view.finalising, false);
  assert.equal(view.error, null);
  assert.equal(view.plans[0].name, "Field");
  assert.equal(view.plans[0].amount, "$25.00");
  assert.equal(view.plans[0].caption, "Billed every month.");
  assert.equal(view.plans[0].current, true);
  assert.equal(view.usage.planName, "Field");
  assert.equal(view.usage.amountDue, "$25.00");
  assert.equal(view.usage.lines[0].item, "Seats");
  assert.equal(view.usage.lines[0].quantity, "2");
  assert.equal(view.invoices[0].status, "Paid");
  assert.equal(view.invoices[0].href, "https://invoice.stripe.com/i/acct_fixture/test");
  assert.equal(JSON.stringify(view).includes(KEY), false);
  assert.ok(calls.length > 0);
  assert.ok(calls.every((call) => call.url.startsWith("https://api.stripe.com/v1/")));
  assert.ok(calls.every((call) => call.authorization === `Bearer ${KEY}`));
  assert.ok(calls.some((call) => call.url.includes(TENANT)));
});

test("a rejected Stripe key does not surface a made-up plan", async () => {
  const fetchImpl: FetchLike = async () => json({ error: { message: KEY } }, 401);
  const view = await loadBilling(TENANT, {
    fetch: fetchImpl,
    env: { STRIPE_SECRET_KEY: KEY, STRIPE_PLAN_PRICE_IDS: "price_fixture" },
  });
  assert.equal(view.error, COPY.loadError);
  assert.equal(view.plans.length, 0);
  assert.equal(JSON.stringify(view).includes(KEY), false);
  assert.equal(JSON.stringify(view).includes("$"), false);
});

test("checkout uses only an allowed price and a Stripe-hosted url", async () => {
  let called = false;
  const blocked: FetchLike = async () => {
    called = true;
    throw new Error("network");
  };
  const refused = await createCheckoutUrl(TENANT, "price_other", "https://app.tervory.com", {
    fetch: blocked,
    env: { STRIPE_SECRET_KEY: KEY, STRIPE_PLAN_PRICE_IDS: "price_fixture" },
  });
  assert.equal(refused, null);
  assert.equal(called, false);

  const bodies: string[] = [];
  const fetchImpl: FetchLike = async (url, init) => {
    bodies.push(init?.body ?? "");
    if (url.endsWith("/prices/price_fixture")) {
      return json({
        id: "price_fixture",
        unit_amount: 2500,
        currency: "usd",
        recurring: { interval: "month", interval_count: 1, usage_type: "metered" },
      });
    }
    if (url.includes("/customers/search")) return json({ data: [] });
    if (url.endsWith("/customers")) return json({ id: "cus_fixture" });
    if (url.endsWith("/checkout/sessions")) {
      return json({ url: "https://checkout.stripe.com/c/pay/cs_test_fixture" });
    }
    return json(null, 500);
  };
  const url = await createCheckoutUrl(TENANT, "price_fixture", "https://app.tervory.com", {
    fetch: fetchImpl,
    env: { STRIPE_SECRET_KEY: KEY, STRIPE_PLAN_PRICE_IDS: "price_fixture" },
  });
  assert.equal(url, "https://checkout.stripe.com/c/pay/cs_test_fixture");
  const session = new URLSearchParams(bodies.at(-1));
  assert.equal(session.get("mode"), "subscription");
  assert.equal(session.get("line_items[0][price]"), "price_fixture");
  assert.equal(session.get("line_items[0][quantity]"), null);
  assert.equal(session.get("metadata[tenant_id]"), TENANT);
  assert.equal(session.get("success_url"), "https://app.tervory.com/billing?tab=plans&checkout=success");
  assert.equal(bodies.some((body) => body.includes(KEY)), false);

  const swapped: FetchLike = async (url) => {
    if (url.endsWith("/checkout/sessions")) return json({ url: "https://evil.example/pay" });
    if (url.includes("/customers/search")) return json({ data: [{ id: "cus_fixture" }] });
    return json({
      id: "price_fixture",
      unit_amount: 2500,
      currency: "usd",
      recurring: { interval: "month", interval_count: 1, usage_type: "licensed" },
    });
  };
  const bad = await createCheckoutUrl(TENANT, "price_fixture", "https://app.tervory.com", {
    fetch: swapped,
    env: { STRIPE_SECRET_KEY: KEY, STRIPE_PLAN_PRICE_IDS: "price_fixture" },
  });
  assert.equal(bad, null);
});

test("checkout notices stay in plain English", () => {
  assert.equal(checkoutNotice("success"), "Stripe is confirming the plan. Refresh if it is not listed yet.");
  assert.equal(checkoutNotice("cancel"), "No plan was changed.");
  assert.equal(checkoutNotice("nope"), null);
});

test("the billing screen does not ship a secret or a made-up price", () => {
  const billing = readFileSync(new URL("../../workspace/app/billing/billing.ts", import.meta.url), "utf8");
  const screen = readFileSync(new URL("../../workspace/app/billing/screen.tsx", import.meta.url), "utf8");
  const page = readFileSync(new URL("../../workspace/app/billing/page.tsx", import.meta.url), "utf8");
  const example = readFileSync(new URL("../../.env.example", import.meta.url), "utf8");
  for (const source of [billing, screen, page, example]) {
    assert.equal(source.includes("sk_live_"), false);
    assert.equal(source.includes("pk_live_"), false);
    assert.equal(source.includes("NEXT_PUBLIC_STRIPE"), false);
  }
  assert.equal(/\$\d/.test(screen), false);
  assert.match(billing, /Pricing is being finalised\./);
  assert.equal(page.includes("@/lib/tank"), false);
  for (const name of ["STRIPE_SECRET_KEY", "STRIPE_PLAN_PRICE_IDS", "BILLING_PUBLIC_ORIGIN"]) {
    const line = example.split("\n").find((item) => item.startsWith(`${name}=`));
    assert.equal(line, `${name}=`);
  }
});
