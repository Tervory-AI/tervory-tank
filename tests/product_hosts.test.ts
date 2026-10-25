import assert from "node:assert/strict";
import { test } from "node:test";
import {
  WORKSPACE_PRODUCT_HOSTS,
  isAutumbraHost,
  mootCanonicalRedirectUrl,
  normalizeHost,
  productHostFor,
  productHostRewritePath,
} from "../workspace/lib/product-hosts.ts";

test("normalizeHost strips port and case", () => {
  assert.equal(normalizeHost("Protect.Tervory.com:443"), "protect.tervory.com");
  assert.equal(normalizeHost(" app.tervory.com "), "app.tervory.com");
  assert.equal(normalizeHost(null), "");
});

test("every mapped product host rewrites root to its path", () => {
  for (const row of WORKSPACE_PRODUCT_HOSTS) {
    assert.equal(productHostRewritePath(row.host, "/"), row.rootPath, row.host);
    assert.equal(productHostRewritePath(`${row.host}:443`, "/"), row.rootPath);
  }
});

test("protect and autumbra both land on public Autumbra product page", () => {
  assert.equal(productHostRewritePath("protect.tervory.com", "/"), "/autumbra");
  assert.equal(productHostRewritePath("autumbra.tervory.com", "/"), "/autumbra");
  assert.equal(isAutumbraHost("protect.tervory.com"), true);
  assert.equal(isAutumbraHost("autumbra.tervory.com"), true);
  assert.equal(isAutumbraHost("zenas.tervory.com"), false);
});

test("app and unknown hosts do not rewrite", () => {
  assert.equal(productHostRewritePath("app.tervory.com", "/"), null);
  assert.equal(productHostRewritePath("rig.tervory.com", "/"), null);
  assert.equal(productHostRewritePath("mcp.tervory.com", "/"), null);
  assert.equal(productHostRewritePath("tervory.com", "/"), null);
  assert.equal(productHostFor("app.tervory.com"), null);
});

test("public and deep paths on product hosts are not rewritten", () => {
  assert.equal(productHostRewritePath("base.tervory.com", "/sign-in"), null);
  assert.equal(productHostRewritePath("base.tervory.com", "/sign-up/continue"), null);
  assert.equal(productHostRewritePath("base.tervory.com", "/api/health"), null);
  assert.equal(productHostRewritePath("base.tervory.com", "/base"), null);
  assert.equal(productHostRewritePath("base.tervory.com", "/base/foo"), null);
  assert.equal(productHostRewritePath("protect.tervory.com", "/admin/autumbra"), null);
  assert.equal(productHostRewritePath("protect.tervory.com", "/autumbra"), null);
  assert.equal(productHostRewritePath("protect.tervory.com", "/admin/ghost"), null);
  assert.equal(productHostRewritePath("zenas.tervory.com", "/moot"), null);
  assert.equal(productHostRewritePath("zenas.tervory.com", "/moot/fixture-published"), null);
  assert.equal(productHostRewritePath("zenas.tervory.com", "/zenas"), null);
});

test("zenas product host root lands on Moot; Zenas panel stays a deep link", () => {
  assert.equal(productHostRewritePath("zenas.tervory.com", "/"), "/moot");
  assert.equal(productHostRewritePath("market-lab.tervory.com", "/"), "/market-lab");
  assert.equal(productHostRewritePath("skala.tervory.com", "/"), "/skala");
  assert.equal(productHostRewritePath("tank.tervory.com", "/"), "/tank");
});

test("app /moot redirects canonically to zenas host", () => {
  assert.equal(
    mootCanonicalRedirectUrl("app.tervory.com", "/moot"),
    "https://zenas.tervory.com/moot",
  );
  assert.equal(
    mootCanonicalRedirectUrl("app.tervory.com", "/moot/fixture-published", "?x=1"),
    "https://zenas.tervory.com/moot/fixture-published?x=1",
  );
  assert.equal(mootCanonicalRedirectUrl("zenas.tervory.com", "/moot"), null);
  assert.equal(mootCanonicalRedirectUrl("app.tervory.com", "/matters"), null);
  assert.equal(mootCanonicalRedirectUrl("app.tervory.com", "/zenas"), null);
});

test("on a squad product host, the root page keeps its own left panel", async () => {
  const { usesOwnShell } = await import("../workspace/app/product-nav.ts");
  for (const host of ["base.tervory.com", "tiger.tervory.com", "market-lab.tervory.com", "tisan.tervory.com", "radix.tervory.com", "skala.tervory.com", "tank.tervory.com"]) {
    const shown = productHostRewritePath(host, "/") ?? "/";
    assert.equal(usesOwnShell(shown), true, host);
  }
  // app.tervory.com/ is the dashboard and keeps the workspace sidebar.
  assert.equal(usesOwnShell(productHostRewritePath("app.tervory.com", "/") ?? "/"), false);
});
