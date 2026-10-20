import assert from "node:assert/strict";
import { test } from "node:test";
import { emptyFlags } from "./catalog";
import { formatDay, formatRefreshed } from "./format";
import { readFlags, scrubSecrets } from "./load";
import { buildPage, feedsToCall } from "./model";
import {
  REFERENCE_LABEL,
  NEED_FILE,
  NEED_KEY,
  NEED_LINK,
  NEED_MCP,
  VAULT_OFF_MESSAGE,
  clientPluginState,
  flagsWithVault,
  groundQuestion,
  mapVaultPayload,
  searchMarketLab,
} from "./plugins";
import { exactNumber, parseAlerts, parseEia, parseFred, parseWorldBank } from "./parse";

test("a missing key keeps the feed off, uncalled, and ignores a stored reading", () => {
  const reading = "4.102";
  const page = buildPage(emptyFlags(), { eia_diesel: { headline: reading, detail: "week" } }, {}, {});
  assert.equal(page.onCount, 9);
  assert.equal(page.offCount, 12);
  assert.equal(page.linkedCount, 13);
  assert.equal(page.featured.some((card) => card.id === "eia_diesel"), false);
  assert.equal(JSON.stringify(page.cards).includes(reading), false);
  const row = page.off.find((item) => item.id === "eia_diesel");
  assert.equal(row?.keyName, "EIA_API_KEY");
  assert.equal(row?.title, "EIA on-highway diesel");
  assert.equal(feedsToCall(emptyFlags()).includes("eia_diesel"), false);
  assert.equal(feedsToCall(emptyFlags()).some((id) => id.startsWith("fred_")), false);
  assert.equal(feedsToCall(emptyFlags()).includes("ups_hazmat"), false);
  assert.equal(feedsToCall(emptyFlags()).length, 9);
});

test("a set EIA key turns that feed on and leaves the others off", () => {
  const flags = emptyFlags();
  flags.EIA_API_KEY = true;
  const page = buildPage(flags, { eia_diesel: { headline: "$4.102", detail: "dollars per gallon, week of 14 Oct 2026" } }, {}, {});
  assert.equal(page.onCount, 10);
  assert.equal(page.offCount, 11);
  assert.equal(page.off.some((row) => row.id === "eia_diesel"), false);
  assert.equal(page.featured[0]?.id, "eia_diesel");
  assert.equal(page.featured[0]?.headline, "$4.102");
  assert.deepEqual(feedsToCall(flags).filter((id) => id === "eia_diesel"), ["eia_diesel"]);
});

test("FRED stays one off row of seven series until its key is set", () => {
  const off = buildPage(emptyFlags(), {}, {}, {});
  assert.equal(off.off[0]?.id, "fred");
  assert.equal(off.off[0]?.title, "FRED economic series (7)");
  assert.equal(off.off[0]?.keyName, "FRED_API_KEY");
  assert.equal(off.cards.some((card) => card.id === "fred"), false);

  const flags = emptyFlags();
  flags.FRED_API_KEY = true;
  const on = buildPage(
    flags,
    {
      fred_tsifrght: { headline: "120.5" },
      fred_gasdesw: { headline: "4.102" },
    },
    {},
    {},
  );
  assert.equal(on.onCount, 16);
  assert.equal(on.offCount, 5);
  assert.equal(on.off.some((row) => row.id === "fred"), false);
  const card = on.cards.find((item) => item.id === "fred");
  assert.equal(card?.lines[0]?.label, "Freight index");
  assert.equal(card?.lines[0]?.value, "120.5");
  assert.equal(card?.lines.at(-1)?.label, "Diesel");
  assert.equal(card?.lines.at(-1)?.value, "4.102");
  const called = feedsToCall(flags);
  assert.equal(called.filter((id) => id.startsWith("fred_")).length, 7);
  assert.equal(called.includes("legiscan"), false);
});

test("a failed check keeps the last good value and names both dates", () => {
  const flags = emptyFlags();
  flags.EIA_API_KEY = true;
  const page = buildPage(
    flags,
    {
      eia_diesel: {
        headline: "$4.102",
        detail: "dollars per gallon, week of 1 Oct 2026",
        failed: true,
        checkedAt: "2026-10-14",
        goodAt: "2026-10-01",
      },
    },
    {},
    {},
  );
  const card = page.featured[0];
  assert.equal(card?.headline, "$4.102");
  assert.equal(
    card?.problem,
    "The last check on 14 Oct 2026 did not work. The source did not answer in time. Showing the last good data, from 1 Oct 2026.",
  );
});

test("a failed check with no earlier success shows no number", () => {
  const page = buildPage(
    emptyFlags(),
    { federal_register: { failed: true, checkedAt: "2026-10-14", notices: [{ title: "Invented notice", meta: "Notice" }] } },
    {},
    {},
  );
  const card = page.featured[0];
  assert.equal(card?.notices.length, 0);
  assert.equal(card?.headline, null);
  assert.match(card?.problem ?? "", /14 Oct 2026/);
  assert.equal(page.onEmpty, false);
});

test("no readings leave the on section empty, and a store error is its own state", () => {
  const empty = buildPage(emptyFlags(), {}, {}, {});
  assert.equal(empty.onEmpty, true);
  assert.equal(empty.loadError, false);
  assert.equal(empty.refreshedLabel, "Not refreshed yet");
  const dumped = JSON.stringify(empty);
  assert.equal(dumped.includes("3" + ".71"), false);
  assert.equal(dumped.includes("52" + "418"), false);

  const broken = buildPage(emptyFlags(), { noaa_alerts: { headline: "12" } }, {}, { error: true });
  assert.equal(broken.loadError, true);
  assert.equal(broken.onEmpty, false);
});

test("linked pages count checks without inventing a change", () => {
  const page = buildPage(
    emptyFlags(),
    {},
    {
      ups_hazmat: { events: 0 },
      fedex_hazmat: { events: 1, latest: "2026-10-14" },
      usps_pub52: { events: 2, latest: "2026-10-02" },
    },
    {},
  );
  const carrier = page.groups.find((group) => group.id === "carrier");
  assert.equal(carrier?.pages.length, 4);
  assert.equal(carrier?.pages[0]?.note, "Not checked yet");
  assert.equal(carrier?.pages[1]?.note, "Checked 14 Oct 2026");
  assert.equal(carrier?.pages[2]?.note, "Changed 2 Oct 2026");
  const ports = page.groups.find((group) => group.id === "ports");
  assert.equal(ports?.pages[0]?.note, "Opens polb.com");
  assert.equal(ports?.pages[1]?.note, "Opens data.ny.gov");
  assert.equal(page.groups.find((group) => group.id === "season")?.pages[0]?.label, "California");
});

test("numbers stay exact and blank FRED values are skipped", () => {
  assert.equal(exactNumber("1.23450"), "1.23450");
  assert.equal(exactNumber("."), null);
  assert.equal(exactNumber(""), null);
  assert.equal(exactNumber(12), "12");
  assert.deepEqual(parseEia({ response: { data: [{ period: "2026-10-12", value: "4.102" }] } }), {
    value: "4.102",
    period: "2026-10-12",
  });
  assert.equal(parseFred({ observations: [{ date: "2026-09-01", value: "." }, { date: "2026-08-01", value: "120.5" }] })?.value, "120.5");
  assert.equal(parseWorldBank([{ page: 1 }, [{ date: "2024", value: "8100.5" }]], "PCOPPUSDM")?.value, "8100.5");
  assert.deepEqual(parseAlerts({ features: [{ properties: { event: "Small Craft Advisory" } }, { properties: {} }] }), {
    count: 2,
    example: "Small Craft Advisory",
  });
});

test("dates do not shift with the timezone", () => {
  assert.equal(formatDay("2026-10-01"), "1 Oct 2026");
  assert.equal(formatRefreshed("not-a-date"), "Not refreshed yet");
  assert.equal(formatRefreshed("2026-10-17T12:40:00.000Z"), "17 Oct 2026, 5:40 AM PT");
});

test("off feeds follow the panel order, with FRED as one row", () => {
  const page = buildPage(emptyFlags(), {}, {}, {});
  assert.deepEqual(
    page.off.map((row) => row.id),
    ["fred", "census_population", "census_trade", "eia_diesel", "noaa_climate", "legiscan"],
  );
});

test("search hits feeds and linked pages, and skips a question with no reading", () => {
  const page = buildPage(
    emptyFlags(),
    { noaa_alerts: { headline: "12", detail: "active alerts", goodAt: "2026-10-03" } },
    {},
    {},
  );
  const weather = searchMarketLab(page, "weather alerts");
  assert.equal(weather.onIds.includes("noaa_alerts"), true);
  assert.equal(weather.offIds.includes("eia_diesel"), false);
  const diesel = searchMarketLab(page, "on-highway");
  assert.deepEqual(diesel.offIds, ["eia_diesel"]);
  const seasons = searchMarketLab(page, "California");
  assert.equal(seasons.linkIds.includes("season_ca"), true);
  const grounded = groundQuestion(page, "severe weather");
  assert.equal(grounded.sources.length, 1);
  assert.equal(grounded.sources[0]?.name.includes("Severe-weather alerts"), true);
  assert.equal(grounded.sources[0]?.date, "3 Oct 2026");
  assert.equal(groundQuestion(page, "zzzz-no-such-feed").sources.length, 0);
  assert.equal(REFERENCE_LABEL, "Sources");
});

test("plugin state sent to the browser is a set of booleans and never a saved secret", () => {
  const flags = readFlags({ EIA_API_KEY: "example-key" } as unknown as NodeJS.ProcessEnv);
  const state = clientPluginState(flags);
  assert.equal(state.title, "Plugins");
  assert.equal(state.keys.find((row) => row.name === "EIA_API_KEY")?.connected, true);
  assert.equal(state.keys.find((row) => row.name === "FRED_API_KEY")?.connected, false);
  assert.equal(state.files.length, 0);
  assert.equal(state.links.length, 0);
  assert.equal(state.connections.length, 0);
  const dumped = JSON.stringify(state);
  assert.equal(dumped.includes("example-key"), false);
  assert.match(NEED_KEY, /Nothing was stored/);
  assert.match(NEED_FILE, /Nothing was saved/);
  assert.match(NEED_LINK, /Nothing was saved/);
  assert.match(NEED_MCP, /Nothing was saved/);
  assert.equal(NEED_KEY.includes("saved 17"), false);
});

test("a vault key turns a feed on only while that vault is on", () => {
  const flags = emptyFlags();
  const off = flagsWithVault(flags, { enabled: false, names: ["FRED_API_KEY", "EIA_API_KEY"] });
  assert.equal(off.FRED_API_KEY, false);
  assert.equal(off.EIA_API_KEY, false);
  assert.equal(feedsToCall(off).some((id) => id.startsWith("fred_")), false);
  const on = flagsWithVault(flags, { enabled: true, names: ["FRED_API_KEY"] });
  assert.equal(on.FRED_API_KEY, true);
  assert.equal(on.EIA_API_KEY, false);
  assert.equal(feedsToCall(on).filter((id) => id.startsWith("fred_")).length, 7);
  const env = emptyFlags();
  env.EIA_API_KEY = true;
  const both = flagsWithVault(env, { enabled: false, names: [] });
  assert.equal(both.EIA_API_KEY, true);
});

test("an off vault shows the plain sentence and drops any secret that arrived with it", () => {
  const secret = "vault-secret-value-9f3a";
  const panel = mapVaultPayload({
    enabled: false,
    message: VAULT_OFF_MESSAGE,
    secrets: [{ name: "FRED_API_KEY", purpose: "FRED", mask: "••••••••", saved_at: "2026-10-17", value: secret }],
    files: [{ id: "1", name: "secret.csv", content: secret }],
  });
  assert.equal(panel.enabled, false);
  assert.equal(panel.message, VAULT_OFF_MESSAGE);
  assert.equal(panel.secrets.length, 0);
  assert.equal(panel.files.length, 0);
  assert.equal(JSON.stringify(panel).includes(secret), false);
  const open = mapVaultPayload({
    enabled: true,
    secrets: [{ name: "FRED_API_KEY", purpose: "FRED", mask: "••••••••", saved_at: "2026-10-17T00:00:00Z", value: secret }],
    connections: [{ id: "c1", name: "Catalogue", server_url: "https://example.com", auth_type: "token", has_token: true, token: secret }],
  });
  assert.equal(open.secrets[0]?.mask, "••••••••");
  assert.equal(open.connections[0]?.hasToken, true);
  assert.equal(JSON.stringify(open).includes(secret), false);
});

test("key flags are booleans and secret text is stripped before it can leave the server", () => {
  const flags = readFlags({ EIA_API_KEY: "example-key" } as unknown as NodeJS.ProcessEnv);
  assert.equal(flags.EIA_API_KEY, true);
  assert.equal(flags.FRED_API_KEY, false);
  assert.equal(JSON.stringify(flags).includes("example-key"), false);
  const clean = scrubSecrets({ headline: "value example-key tail", note: "api_key=example-key" }, ["example-key"]);
  assert.equal(clean.headline.includes("example-key"), false);
  assert.equal(clean.note.includes("example-key"), false);
});
