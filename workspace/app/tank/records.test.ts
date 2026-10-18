import assert from "node:assert/strict";
import { test } from "node:test";
import { groundAsk, hideKeys } from "./ask";
import { searchTank, TANK_RECORDS, VAULT_LINE } from "./records";

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
  assert.match(VAULT_LINE, /Squads cannot read it/);
  assert.equal(/sk-|BEGIN |eyJ/.test(VAULT_LINE), false);
  for (const record of TANK_RECORDS) {
    assert.equal(record.detail.includes("sk-"), false);
    assert.equal(/[A-Za-z0-9]{24,}/.test(record.detail), false);
  }
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
