/* Actual server actions and public route, with named identity/fetch substitutes. */
const assert = require("node:assert/strict");
const {
  workspace,
} = require("../command_acceptance_20261031/workspace_loader.cjs");
const id = "00000000-0000-0000-0000-000000000411";
const token = "tb1.za." + "a".repeat(32) + ".rk_pub_" + "b".repeat(48),
  origin = "https://store.placeholder.invalid";
(async () => {
  const calls = [],
    load = workspace({
      env: {
        TANK_URL: "https://us.placeholder.invalid",
        TANK_URL_ZA: "https://za.placeholder.invalid",
      },
      fetch: async (url, init) => {
        calls.push({ url: String(url), init });
        return Response.json(
          { name: "placeholder store" },
          { headers: { "Access-Control-Allow-Origin": origin } },
        );
      },
    });
  const configuration = load("next.config.ts").default;
  const fontHeaders = (await configuration.headers()).find(
    (row) =>
      row.source ===
      "/trigger/:font(AtkinsonHyperlegible-Regular|Literata).ttf",
  );
  assert.equal(
    fontHeaders.headers.find((row) => row.key === "Access-Control-Allow-Origin")
      .value,
    "*",
  );
  const route = load("app/v1/bot/widget/[operation]/route.ts");
  const request = () =>
    new Request("https://workspace.placeholder.invalid/v1/bot/widget/config", {
      method: "POST",
      headers: {
        origin,
        "x-bot-key": token,
        "content-type": "application/json",
        "x-forwarded-for": "192.0.2.4",
        "x-tank-key": "placeholder injected private key",
      },
      body: "{}",
    });
  assert.equal((await route.OPTIONS(request())).status, 204);
  assert.equal(
    (
      await route.POST(request(), {
        params: Promise.resolve({ operation: "config" }),
      })
    ).status,
    200,
  );
  assert.equal(
    calls[0].url,
    "https://za.placeholder.invalid/v1/bot/widget/config",
  );
  assert.equal(calls[0].init.headers.origin, origin);
  assert.equal(calls[0].init.headers["x-tank-key"], undefined);
  assert.equal(calls[0].init.headers["x-bot-key"], token);
  assert.equal(calls[0].init.redirect, "error");
  assert.equal(
    (
      await route.POST(request(), {
        params: Promise.resolve({ operation: "placeholder-forbidden" }),
      })
    ).status,
    404,
  );
  assert.equal(calls.length, 1);
  const isolated = workspace({
    env: { TANK_URL: "https://us.placeholder.invalid" },
    fetch: () => {
      throw Error("placeholder must never fallback");
    },
  })("app/v1/bot/widget/[operation]/route.ts");
  assert.equal(
    (
      await isolated.POST(request(), {
        params: Promise.resolve({ operation: "message" }),
      })
    ).status,
    503,
  );
  const actionsCalls = [];
  const actions = workspace({
    env: {},
    fetch: () => {
      throw Error("placeholder unexpected fetch");
    },
    mocks: {
      "@clerk/nextjs/server": { auth: async () => ({ orgRole: "org:admin" }) },
      "@/lib/tenant": {
        activeTenant: async () => ({
          tenantId: id,
          userId: "placeholder-user",
          orgName: "placeholder store",
          orgId: "org_placeholder",
        }),
      },
      "@/lib/tank": {
        commandRequest: async (identity, path, init) => {
          actionsCalls.push({ identity, path, init });
          return Response.json(
            path.endsWith("settings")
              ? { settings: { enabled: false } }
              : { status: "confirmed" },
          );
        },
      },
    },
  })("app/trigger/actions.ts");
  const settings = await actions.readTrigger("bot/settings");
  assert.equal(settings.settings.name, "placeholder store");
  await actions.proposeTrigger("trigger.bot.settings", { enabled: false });
  await actions.confirmTrigger(id, id);
  assert.equal(actionsCalls[2].path, "cards/" + id);
  assert.equal(JSON.parse(actionsCalls[2].init.body).action, "confirm");
  assert.equal(actionsCalls[0].identity.tenantAdmin, true);
  assert.equal(actionsCalls[0].identity.tenantId, id);
  await assert.rejects(() =>
    actions.readTrigger("bot/settings?tenant_id=placeholder-other"),
  );
  assert.equal(actionsCalls.length, 3);
  console.log(
    "PASS actual public regional transport, no private key, no region fallback, bounded operation allowlist, active-tenant server actions and canonical Confirm route. Placeholder fixtures only.",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
