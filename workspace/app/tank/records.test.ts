import assert from "node:assert/strict";
import { test } from "node:test";
import { groundAsk, hideKeys } from "./ask";
import { modelRows, MODEL_ROSTER } from "./models";
import { searchTank, TANK_RECORDS, VAULT_LINE } from "./records";
import { pipelineTo, SQUADS, SQUAD_LINE } from "./squads";

test("an empty search shows nothing", () => {
  assert.deepEqual(searchTank("   "), []);
});

test("search stays inside Tank's own records", () => {
  const hits = searchTank("ledger");
  assert.deepEqual(hits.map((hit) => hit.id), ["ledger"]);
  assert.equal(hits[0]?.href, "/ledger");
  const vault = searchTank("vault");
  assert.ok(vault.every((hit) => hit.title === "tank.vault" || hit.detail.includes("tank.vault")));
  assert.equal(vault.some((hit) => /sk-|api[_-]?key|secret/i.test(hit.detail)), false);
});

test("the vault line names tank.vault and no key", () => {
  assert.match(VAULT_LINE, /tank\.vault is always on/);
  assert.match(VAULT_LINE, /cannot read the platform keys/);
  assert.match(SQUAD_LINE, /another squad's vault/);
  assert.equal(/sk-|BEGIN |eyJ/.test(VAULT_LINE + SQUAD_LINE), false);
  for (const record of TANK_RECORDS) {
    assert.equal(record.detail.includes("sk-"), false);
    assert.equal(/[A-Za-z0-9]{24,}/.test(record.detail), false);
  }
});

test("each agent has one box and a pipeline, and a missing key is only a flag", () => {
  assert.deepEqual(
    SQUADS.map((squad) => squad.name),
    ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas", "Skala", "Tank"],
  );
  assert.equal(pipelineTo("Base"), "Pipeline to Base");
  const secret = "sk-live_secretvalue";
  const rows = modelRows({
    OPENAI_API_KEY: secret,
    GEMINI_API_KEY: " ",
    XAI_API_KEY: "",
  });
  assert.equal(rows.length, MODEL_ROSTER.length);
  assert.equal(JSON.stringify(rows).includes(secret), false);
  assert.equal(JSON.stringify(rows).includes("OPENAI_API_KEY"), false);
  assert.equal(rows.find((row) => row.name === "luna")?.keyMissing, false);
  assert.equal(rows.find((row) => row.name === "haiku")?.keyMissing, true);
  assert.equal(rows.find((row) => row.name === "flash")?.keyMissing, true);
  assert.equal(rows.find((row) => row.name === "grok")?.keyMissing, true);
});

test("Ask Tank hides a key and refuses to pass one through", () => {
  const leaked = "the key is sk-live_secretvalue please";
  assert.equal(hideKeys(leaked).includes("sk-"), false);
  assert.match(hideKeys(leaked), /\[hidden\]/);
  const grounded = groundAsk([{ role: "user", content: leaked }]);
  assert.equal(grounded[0]?.content.includes("sk-"), false);
  assert.match(grounded[0]?.content ?? "", /another squad's vault/);
  assert.match(grounded[0]?.content ?? "", /tank\.vault is always on/);
});
