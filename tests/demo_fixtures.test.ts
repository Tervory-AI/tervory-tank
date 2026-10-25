import assert from "node:assert/strict";
import { test } from "node:test";
import { DEMO_BANNER, DEMO_PRODUCTS, demoProductFor, demoProductIsFull } from "../workspace/lib/demo-fixtures.ts";
import { WORKSPACE_PRODUCT_HOSTS } from "../workspace/lib/product-hosts.ts";

test("every squad product host has a full demo fixture", () => {
  for (const row of WORKSPACE_PRODUCT_HOSTS.filter((r) => r.product !== "Autumbra")) {
    const product = demoProductFor(row.rootPath.slice(1));
    assert.ok(product, row.host);
    assert.ok(demoProductIsFull(product), row.host);
  }
});

test("fixtures have unique ids per section and an example banner", () => {
  assert.match(DEMO_BANNER, /not live client data/);
  for (const p of DEMO_PRODUCTS) {
    for (const s of p.sections) assert.equal(new Set(s.items.map((i) => i.id)).size, s.items.length, p.slug);
  }
  assert.equal(demoProductFor("nope"), null);
});
