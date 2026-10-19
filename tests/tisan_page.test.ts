import assert from "node:assert/strict";
import { test } from "node:test";
import { primaryAction, resultSummary, searchRecords } from "../workspace/app/tisan/copy.ts";
import { mapVaultPayload, offPanel, TISAN_VAULT, VAULT_OFF_MESSAGE } from "../workspace/app/tisan/vault-model.ts";

test("search finds the landing builds, page and tests", () => {
  assert.deepEqual(searchRecords("landing", "all"), []);
  assert.equal(searchRecords("lighthouse", "Test").length, 0);
  assert.equal(searchRecords("landing", "Page")[0]?.title, undefined);
  assert.deepEqual(searchRecords("   ", "all"), []);
  assert.deepEqual(searchRecords("zzzz-no-match", "all"), []);
  assert.match(resultSummary("landing", 0), /0 results for “landing”/);
  assert.equal(resultSummary("landing", 0).includes("Example"), false);
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

test("an off vault shows the sentence and drops any secret that arrived with it", () => {
  const secret = "vault-secret-value-9f3a";
  assert.equal(TISAN_VAULT, "tisan.vault");
  assert.equal(VAULT_OFF_MESSAGE, "This vault is off. Turn it on in Tank.");
  const panel = mapVaultPayload({
    enabled: false,
    message: VAULT_OFF_MESSAGE,
    secrets: [{ name: "GITHUB_TOKEN", purpose: "Draft requests", mask: "••••••••", saved_at: "2026-10-17", value: secret }],
    files: [{ id: "1", name: "brief.pdf", content: secret }],
    connections: [{ id: "c1", name: "Scan", server_url: "https://example.com", token: secret }],
  });
  assert.equal(panel.enabled, false);
  assert.equal(panel.message, VAULT_OFF_MESSAGE);
  assert.equal(panel.secrets.length, 0);
  assert.equal(panel.files.length, 0);
  assert.equal(panel.connections.length, 0);
  assert.equal(JSON.stringify(panel).includes(secret), false);
  const open = mapVaultPayload({
    enabled: true,
    secrets: [{ name: "GITHUB_TOKEN", purpose: "Draft requests", mask: "••••••••", saved_at: "2026-10-17T00:00:00Z", value: secret }],
    connections: [{ id: "c1", name: "Scan", server_url: "https://example.com", auth_type: "token", has_token: true, token: secret }],
  });
  assert.equal(open.secrets[0]?.mask, "••••••••");
  assert.equal(open.connections[0]?.hasToken, true);
  assert.equal(JSON.stringify(open).includes(secret), false);
  assert.equal(JSON.stringify(offPanel()).includes(secret), false);
});
