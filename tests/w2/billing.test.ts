import assert from "node:assert/strict";
import { createRequire } from "node:module";
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
import { receiveStripeWebhook, tankWebhookStore } from "../../workspace/app/billing/webhook.ts";

const requireFromWorkspace = createRequire(new URL("../../workspace/package.json", import.meta.url));
const Stripe = requireFromWorkspace("stripe");

const KEY = "sk_test_billingfixture";
const TENANT = "7f3b1c2e-9a4d-4c1e-8f2a-5b6d7e8f9a0b";

function json(body: unknown, status = 200): { ok: boolean; status: number; json: () => Promise<unknown>; text: () => Promise<string> } {
  const text = JSON.stringify(body);
  return { ok: status >= 200 && status < 300, status, json: async () => body, text: async () => text };
}

type ClaimCall = { url: string; method: string; body: string; hasKey: boolean };

function tankClaimStandIn() {
  const rows = new Map<string, { type: string; handled: boolean }>();
  const calls: ClaimCall[] = [];
  const previous = globalThis.fetch;
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? init.body : "";
    const headers = new Headers(init?.headers);
    calls.push({ url, method, body, hasKey: headers.has("x-tank-key") });
    const parsed = JSON.parse(body) as { event_id?: string; type?: string };
    const eventId = parsed.event_id ?? "";
    if (url.endsWith("/v1/billing/events/claim")) {
      const existing = rows.get(eventId);
      if (existing) return json({ first: false });
      rows.set(eventId, { type: parsed.type ?? "", handled: false });
      return json({ first: true });
    }
    if (url.endsWith("/v1/billing/events/release")) {
      const existing = rows.get(eventId);
      if (existing && existing.handled === false) rows.delete(eventId);
      return json({ released: Boolean(existing && existing.handled === false) });
    }
    if (url.endsWith("/v1/billing/events/handled")) {
      const existing = rows.get(eventId);
      if (existing) existing.handled = true;
      return json({ handled: Boolean(existing) });
    }
    throw new Error("unexpected tank call");
  };
  return {
    calls,
    rows,
    restore() {
      globalThis.fetch = previous;
    },
  };
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
  for (const name of ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PLAN_PRICE_IDS", "BILLING_PUBLIC_ORIGIN"]) {
    const line = example.split("\n").find((item) => item.startsWith(`${name}=`));
    assert.equal(line, `${name}=`);
  }
});

const WEBHOOK_SECRET = "whsec_test_placeholder";
const STRIPE_EVENT = readFileSync(new URL("../fixtures/stripe/event.json", import.meta.url), "utf8");

function signed(payload: string, secret = WEBHOOK_SECRET, timestamp?: number): string {
  return Stripe.webhooks.generateTestHeaderString({ payload, secret, timestamp });
}

test("Stripe's own event fixture is signed with Stripe's helper and applied once", async () => {
  const fixture = JSON.parse(STRIPE_EVENT);
  assert.equal(fixture.id, "evt_1Pgc76B7WZ01zgkWwyRHS12y");
  assert.equal(fixture.object, "event");
  assert.equal(fixture.type, "plan.created");
  const header = signed(STRIPE_EVENT);
  const seen: { id: string; type: string }[] = [];
  const shared = tankWebhookStore();
  const standin = tankClaimStandIn();
  const effect = (event: { id: string; type: string }) => {
    seen.push(event);
  };
  try {
    const first = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: shared,
      effect,
    });
    const second = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: shared,
      effect,
    });
    const otherInstance = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect,
    });
    const defaultStore = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      effect,
    });
    assert.deepEqual(first, { status: 200, body: { received: true } });
    assert.deepEqual(second, { status: 200, body: { received: true, duplicate: true } });
    assert.deepEqual(otherInstance, { status: 200, body: { received: true, duplicate: true } });
    assert.deepEqual(defaultStore, { status: 200, body: { received: true, duplicate: true } });
    assert.deepEqual(seen, [{ id: fixture.id, type: fixture.type }]);
    const claims = standin.calls.filter((call) => call.url.endsWith("/v1/billing/events/claim"));
    assert.equal(claims.length, 4);
    assert.ok(claims.every((call) => call.method === "POST" && call.hasKey));
    assert.ok(claims.every((call) => call.body.includes(fixture.id) && call.body.includes(fixture.type)));
    assert.ok(claims.every((call) => !call.body.includes(WEBHOOK_SECRET)));
    assert.equal(standin.calls.some((call) => call.url.endsWith("/v1/billing/events/release")), false);
    const handled = standin.calls.filter((call) => call.url.endsWith("/v1/billing/events/handled"));
    assert.equal(handled.length, 1);
    assert.equal(handled[0].method, "POST");
    assert.equal(handled[0].hasKey, true);
    assert.equal(handled[0].body.includes(WEBHOOK_SECRET), false);
    assert.equal(JSON.stringify(first).includes(WEBHOOK_SECRET), false);
    assert.equal(JSON.stringify(second).includes("2000"), false);
    assert.equal(JSON.stringify(second).includes(fixture.id), false);
    assert.notEqual(shared, tankWebhookStore());
  } finally {
    standin.restore();
  }
});

test("a bad Stripe signature is refused and does not apply the event", async () => {
  let applied = 0;
  let tankCalls = 0;
  const effect = () => {
    applied += 1;
  };
  const previous = globalThis.fetch;
  globalThis.fetch = async () => {
    tankCalls += 1;
    throw new Error("network");
  };
  try {
    const missing = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: null,
      secret: WEBHOOK_SECRET,
      effect,
    });
    const tampered = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT.replace("plan.created", "plan.updated"),
      signature: signed(STRIPE_EVENT),
      secret: WEBHOOK_SECRET,
      effect,
    });
    const wrongSecret = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: signed(STRIPE_EVENT, "whsec_test_other_placeholder"),
      secret: WEBHOOK_SECRET,
      effect,
    });
    const stale = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: signed(STRIPE_EVENT, WEBHOOK_SECRET, Math.floor(Date.now() / 1000) - 3600),
      secret: WEBHOOK_SECRET,
      effect,
    });
    const unconfigured = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: signed(STRIPE_EVENT),
      secret: "  ",
      effect,
    });
    assert.equal(missing.status, 400);
    assert.equal(tampered.status, 400);
    assert.equal(wrongSecret.status, 400);
    assert.equal(stale.status, 400);
    assert.equal(unconfigured.status, 500);
    assert.equal(applied, 0);
    assert.equal(tankCalls, 0);
    for (const result of [missing, tampered, wrongSecret, stale, unconfigured]) {
      assert.equal(JSON.stringify(result).includes(WEBHOOK_SECRET), false);
      assert.equal(JSON.stringify(result).includes("whsec_test_other_placeholder"), false);
    }
  } finally {
    globalThis.fetch = previous;
  }
});

test("a failed webhook releases the event id so Stripe's retry runs once", async () => {
  let calls = 0;
  const failOnce = () => {
    calls += 1;
    if (calls === 1) throw new Error("not stored");
  };
  const header = signed(STRIPE_EVENT);
  const standin = tankClaimStandIn();
  try {
    const failed = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: failOnce,
    });
    const retried = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: failOnce,
    });
    const again = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: failOnce,
    });
    assert.equal(failed.status, 500);
    assert.equal(JSON.stringify(failed).includes("not stored"), false);
    assert.deepEqual(retried, { status: 200, body: { received: true } });
    assert.deepEqual(again, { status: 200, body: { received: true, duplicate: true } });
    assert.equal(calls, 2);
    const releases = standin.calls.filter((call) => call.url.endsWith("/v1/billing/events/release"));
    assert.equal(releases.length, 1);
    assert.equal(releases[0].method, "POST");
    assert.equal(releases[0].hasKey, true);
    const handled = standin.calls.filter((call) => call.url.endsWith("/v1/billing/events/handled"));
    assert.equal(handled.length, 1);
    const releaseAt = standin.calls.findIndex((call) => call.url.endsWith("/v1/billing/events/release"));
    const handledAt = standin.calls.findIndex((call) => call.url.endsWith("/v1/billing/events/handled"));
    assert.equal(releaseAt < handledAt, true);
  } finally {
    standin.restore();
  }
});

test("when Tank cannot be reached the webhook answers 500 and does not apply the event", async () => {
  let applied = 0;
  const effect = () => {
    applied += 1;
  };
  const header = signed(STRIPE_EVENT);
  const previous = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new Error("connect ECONNREFUSED");
  };
  try {
    const down = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect,
    });
    globalThis.fetch = async () => json({ error: "unavailable" }, 503);
    const refused = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect,
    });
    globalThis.fetch = async () => json({ ok: true }, 200);
    const unstored = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect,
    });
    assert.equal(down.status, 500);
    assert.equal(refused.status, 500);
    assert.equal(unstored.status, 500);
    assert.equal(applied, 0);
    for (const result of [down, refused, unstored]) {
      assert.equal(result.body.received, undefined);
      assert.equal(JSON.stringify(result).includes(WEBHOOK_SECRET), false);
      assert.equal(JSON.stringify(result).includes("ECONNREFUSED"), false);
      assert.equal(JSON.stringify(result).includes("unavailable"), false);
    }
  } finally {
    globalThis.fetch = previous;
  }
});

test("after a successful event, release does not delete it and a redelivery is a duplicate", async () => {
  const fixture = JSON.parse(STRIPE_EVENT) as { id: string; type: string };
  const header = signed(STRIPE_EVENT);
  const seen: string[] = [];
  const standin = tankClaimStandIn();
  const store = tankWebhookStore();
  try {
    const first = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store,
      effect: (event) => {
        seen.push(event.id);
      },
    });
    await store.release(fixture.id);
    const again = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: (event) => {
        seen.push(event.id);
      },
    });
    assert.deepEqual(first, { status: 200, body: { received: true } });
    assert.deepEqual(again, { status: 200, body: { received: true, duplicate: true } });
    assert.deepEqual(seen, [fixture.id]);
    assert.equal(standin.rows.get(fixture.id)?.handled, true);
    assert.equal(JSON.stringify(again).includes(fixture.id), false);
    assert.equal(JSON.stringify(again).includes(WEBHOOK_SECRET), false);
  } finally {
    standin.restore();
  }
});

test("when marking the event handled fails, the webhook answers 500 and the retry does not run the effect", async () => {
  const header = signed(STRIPE_EVENT);
  let applied = 0;
  const previous = globalThis.fetch;
  const rows = new Map<string, boolean>();
  globalThis.fetch = async (input, init) => {
    const url = String(input);
    const body = typeof init?.body === "string" ? init.body : "";
    const eventId = (JSON.parse(body) as { event_id?: string }).event_id ?? "";
    if (url.endsWith("/v1/billing/events/claim")) {
      if (rows.has(eventId)) return json({ first: false });
      rows.set(eventId, false);
      return json({ first: true });
    }
    if (url.endsWith("/v1/billing/events/handled")) return json({ error: "unavailable" }, 503);
    if (url.endsWith("/v1/billing/events/release")) {
      rows.delete(eventId);
      return json({ released: true });
    }
    throw new Error("unexpected tank call");
  };
  try {
    const failed = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: () => {
        applied += 1;
      },
    });
    const retry = await receiveStripeWebhook({
      rawBody: STRIPE_EVENT,
      signature: header,
      secret: WEBHOOK_SECRET,
      store: tankWebhookStore(),
      effect: () => {
        applied += 1;
      },
    });
    assert.equal(failed.status, 500);
    assert.equal(failed.body.received, undefined);
    assert.deepEqual(retry, { status: 200, body: { received: true, duplicate: true } });
    assert.equal(applied, 1);
    assert.equal(rows.size, 1);
    assert.equal(JSON.stringify(failed).includes(WEBHOOK_SECRET), false);
    assert.equal(JSON.stringify(failed).includes("unavailable"), false);
  } finally {
    globalThis.fetch = previous;
  }
});
