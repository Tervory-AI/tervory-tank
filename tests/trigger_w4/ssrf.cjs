/* Exercise actual server actions -> lib/tank.ts -> fetch; no outside network. */
const assert = require("node:assert/strict");
const path = require("node:path");
const {
  workspace,
} = require("../command_acceptance_20261031/workspace_loader.cjs");
const {legacyHome} = require("../legacy_tenant_home.cjs");
const id = "00000000-0000-0000-0000-000000000411";
const attacks = [
  "../admin",
  "%2e%2e/",
  "x?y",
  "placeholder".repeat(1000),
  "/",
  "..",
  "#",
  "constructor",
  "__proto__",
  "-".repeat(36),
  id + "\n",
  null,
  411,
];
const crm = ["leads", "contacts", "estimates", "invoices"];
const query = [
  ["marketing", "posts"],
  ["marketing", "composer"],
  ["marketing", "calendar"],
  ["marketing", "reviews"],
  ["bot", "inbox"],
];
(async () => {
  const calls = [];
  const homeLookups = [];
  let identities = 0;
  const load = workspace({
    env: {
      TANK_URL: "https://tank.placeholder.invalid",
      TANK_API_KEY: "placeholder-workspace-key",
      TANK_URL_ZA: "https://za.placeholder.invalid",
    },
    fetch: async (url, init) => {
      const home = legacyHome(url, init, {tenants:[id], key:'placeholder-workspace-key', origin:'https://tank.placeholder.invalid', calls:homeLookups});
      if (home) return home;
      calls.push({ url: String(url), init });
      return Response.json({ settings: { enabled: false } });
    },
    mocks: {
      "@/lib/trigger-signin": { auth: async () => ({ orgRole: "org:admin" }) },
      "@/lib/trigger": {triggerIdentity: async tenant => ({...tenant, tenantAdmin:true})},
      "@/lib/tenant": {
        activeTenant: async () => {
          identities++;
          return {
            tenantId: id,
            userId: "placeholder-user",
            orgName: "placeholder store",
          };
        },
      },
      "next/navigation": {
        notFound: () => {
          throw new Error("placeholder-not-found");
        },
      },
      "../records": { default: () => null },
      "../view": { default: () => null },
      "react/jsx-runtime": require(
        path.join(process.env.COMMAND_TEST_TOOLS, "react/jsx-runtime"),
      ),
    },
  });
  const actions = load("app/trigger/actions.ts");
  const refused = async (invoke) => {
    const before = calls.length,
      beforeIdentity = identities, beforeHome = homeLookups.length;
    await assert.rejects(invoke);
    assert.equal(calls.length, before, "malformed value reached fetch");
    assert.equal(homeLookups.length, beforeHome, "malformed value reached the directory");
    assert.equal(
      identities,
      beforeIdentity,
      "malformed value reached identity lookup",
    );
  };
  for (const section of crm) {
    await actions.readTrigger("crm", section);
    assert(homeLookups.length > 0);
    assert.equal(
      calls.at(-1).url,
      `https://tank.placeholder.invalid/v1/command/trigger/console/crm/${section}`,
    );
    await actions.readTrigger("crm", section, id);
    assert.equal(
      calls.at(-1).url,
      `https://tank.placeholder.invalid/v1/command/trigger/console/crm/${section}/${encodeURIComponent(id)}`,
    );
    for (const bad of attacks)
      await refused(() => actions.readTrigger("crm", section, bad));
  }
  for (const [area, section] of query) {
    await actions.readTrigger(area, section, id);
    assert.equal(
      calls.at(-1).url,
      `https://tank.placeholder.invalid/v1/command/trigger/console/${area}/${section}?record_id=${encodeURIComponent(id)}`,
    );
    for (const bad of attacks)
      await refused(() => actions.readTrigger(area, section, bad));
  }
  for (const [area, section] of [
    ["marketing", "channels"],
    ["bot", "settings"],
  ]) {
    await actions.readTrigger(area, section);
    for (const bad of [...attacks, id])
      await refused(() => actions.readTrigger(area, section, bad));
  }
  for (const bad of attacks) {
    for (const area of ["crm", "marketing", "bot"])
      await refused(() => actions.readTrigger(area, bad));
    await refused(() => actions.readTrigger(bad, "leads"));
    await refused(() => actions.readTrigger(bad)); // Removed raw-path server-action shape is also refused.
    await refused(() => actions.confirmTrigger(id, bad));
    await refused(() => actions.confirmTrigger(bad, id));
  }
  await actions.confirmTrigger(id, id);
  assert.equal(
    calls.at(-1).url,
    `https://tank.placeholder.invalid/v1/command/cards/${encodeURIComponent(id)}`,
  );
  assert.equal(JSON.parse(calls.at(-1).init.body).action, "confirm");
  const page = load("app/trigger/[[...segments]]/page.tsx").default;
  for (const bad of attacks.filter((value) => typeof value === "string")) {
    for (const segments of [
      ["crm", bad],
      ["crm", "leads", bad],
      ["marketing", bad],
      ["marketing", "posts", bad],
      ["bot", "inbox", bad],
    ]) {
      await refused(() => page({ params: Promise.resolve({ segments }) }));
    }
  }
  await page({ params: Promise.resolve({ segments: ["crm", "leads", id] }) });
  assert.equal(
    calls.at(-1).url,
    `https://tank.placeholder.invalid/v1/command/trigger/console/crm/leads/${id}`,
  );
  await page({
    params: Promise.resolve({ segments: ["marketing", "posts", id] }),
  });
  assert.equal(
    calls.at(-1).url,
    `https://tank.placeholder.invalid/v1/command/trigger/console/marketing/posts?record_id=${id}`,
  );

  const widgetCalls = [];
  const origin = "https://store.placeholder.invalid",
    key = "tb1.za." + "a".repeat(32) + ".rk_pub_" + "b".repeat(48);
  const route = workspace({
    env: {
      TANK_URL: "https://tank.placeholder.invalid",
      TANK_URL_ZA: "https://za.placeholder.invalid",
    },
    fetch: async (url) => {
      widgetCalls.push(String(url));
      return Response.json(
        { state: "placeholder" },
        { headers: { "Access-Control-Allow-Origin": origin } },
      );
    },
  })("app/v1/bot/widget/[operation]/route.ts");
  const request = () =>
    new Request("https://workspace.placeholder.invalid/v1/bot/widget/config", {
      method: "POST",
      headers: { origin, "content-type": "application/json", "x-bot-key": key },
      body: "{}",
    });
  for (const bad of attacks) {
    const before = widgetCalls.length;
    const response = await route.POST(request(), {
      params: Promise.resolve({ operation: bad }),
    });
    assert.equal(response.status, 404);
    assert.equal(
      widgetCalls.length,
      before,
      "malformed operation reached fetch",
    );
  }
  for (const operation of ["config", "message", "handover", "poll"]) {
    assert.equal(
      (await route.POST(request(), { params: Promise.resolve({ operation }) }))
        .status,
      200,
    );
    assert.equal(
      widgetCalls.at(-1),
      `https://za.placeholder.invalid/v1/bot/widget/${operation}`,
    );
  }
  console.log(
    "PASS every Trigger CRM/list/detail/query/card/widget path rejects traversal, encoded traversal, query injection and over-long values before identity or fetch; constant routes and canonical UUIDs preserve valid requests.",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
