# VENDOR-1: every paid tool call lands on the ledger, with its price

> Written 21 Oct 2026. Base calls Brave Search automatically when our own free search finds nothing (`base.find_site`). Those calls cost real money (they are on the Brave bill), but **none of them is booked on Tank's ledger**. The skill calls Brave directly through the shared HTTP client, and nothing records the spend. That breaks the promise that every paid step has a receipt, and it makes "cost per verified record" too low.
>
> The shared HTTP client already has one hook for paid hosts (`controls.paid_host_hook`, which enforces the founder's pause). Metering belongs in the same place, so no approved skill version is edited.

**Files you may change:**
- new `tank/vendor_meter.py`;
- `tank/controls.py` (call the meter from `paid_host_hook` and the response hook only);
- `tank/main.py` (add a response hook to the existing shared client's `event_hooks`, nothing else);
- `tank/schema.sql` (additive);
- `tank/Dockerfile` (COPY line, standing approval);
- `.env.example` (names only);
- tests.

1. **Meter every request to a paid tool host** on the shared client (today `api.search.brave.com`; the list lives in one place). After the response, write one ledger row:
   - model `vendor:brave.search`, vendor `brave.search`, units 1;
   - `cost_usd` from `tank.price_book` (an expense row "brave.search per query", set by the founder);
   - the task and agent from the run context (the existing `_task` context var), and the tenant and region of the run;
   - outcome `delivered` for a 2xx response, otherwise `failed`. A failed call still costs a query if the provider bills it; follow Brave's billing rule, documented in a comment with its source URL.
2. **No price set yet:** book the row with `cost_usd` NULL and status `unpriced`, never $0. The proof page already shows unpriced rows separately.
3. **Context.dev** (`agents/base/sources/context_dev.py`) already books credits through its own reserve/settle ledger. Add the dollar conversion from the price book (expense row "context.dev per credit") on the same ledger rows, with credits kept as units. Record the Pro list price ($99 for 125,000 credits, from https://www.context.dev/pricing, dated 21 Oct 2026) as the default. A free-pass flag set by the founder shows "free pass, $0 actual" beside it.
4. **Price book entries** are founder-set on the existing admin price book page. No price is hard-coded except the Context.dev list price default above.
5. **Never log** the request URL's query string, headers or keys.

## Done when
CI green. Tests:
- a Brave request writes exactly one vendor row with the price-book price;
- no price means an `unpriced` row, never $0;
- the pause still refuses before any request (and books nothing);
- a non-paid host books nothing;
- Context.dev rows carry both credits and dollars;
- no approved skill file changes.
