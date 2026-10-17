import assert from "node:assert/strict";
import { test } from "node:test";
import { primaryAction, resultSummary, searchRecords } from "../workspace/app/tisan/copy.ts";

test("search finds the landing builds, page and tests", () => {
  const hits = searchRecords("landing", "all");
  assert.equal(hits.length, 5);
  assert.deepEqual(hits.map((row) => row.kind), ["Build", "Build", "Page", "Test", "Test"]);
  assert.equal(searchRecords("lighthouse", "Test").length, 1);
  assert.equal(searchRecords("landing", "Page")[0]?.title, "Landing — Desktop & Mobile");
  assert.deepEqual(searchRecords("   ", "all").map((row) => row.id).length, 10);
  assert.deepEqual(searchRecords("zzzz-no-match", "all"), []);
  assert.match(resultSummary("landing", 5), /5 results for “landing” · Example/);
});

test("the red button follows the view", () => {
  const base = { view: "overview" as const, query: "", filter: "all" as const, dialog: "none" as const, pluginTab: "keys" as const, mobile: false };
  assert.equal(primaryAction(base), "send");
  assert.equal(primaryAction({ ...base, query: "landing" }), "start");
  assert.equal(primaryAction({ ...base, filter: "Build" }), "start");
  assert.equal(primaryAction({ ...base, view: "builds" }), "start");
  assert.equal(primaryAction({ ...base, view: "design" }), "start");
  assert.equal(primaryAction({ ...base, view: "tests" }), "start");
  assert.equal(primaryAction({ ...base, view: "settings" }), "start");
  assert.equal(primaryAction({ ...base, dialog: "build" }), "start-confirm");
  assert.equal(primaryAction({ ...base, dialog: "plugins", pluginTab: "keys" }), "save-key");
  assert.equal(primaryAction({ ...base, dialog: "plugins", pluginTab: "files" }), "choose-files");
  assert.equal(primaryAction({ ...base, dialog: "plugins", pluginTab: "links" }), "add-link");
  assert.equal(primaryAction({ ...base, dialog: "plugins", pluginTab: "mcp" }), "add-connection");
  assert.equal(primaryAction({ ...base, dialog: "plugins", pluginTab: "files", mobile: true }), "save-key");
});
