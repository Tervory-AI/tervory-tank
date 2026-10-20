const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const ts = require(path.join(root, "workspace/node_modules/typescript"));
const source = fs.readFileSync(path.join(root, "workspace/app/tisan/gold-actions.ts"), "utf8");
const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

function actions(userId) {
  const calls = [];
  const exported = {};
  new Function("require", "exports", code)((name) => {
    if (name === "@/lib/tenant") return { activeTenant: async () => ({ tenantId: "workspace-tenant", userId }) };
    if (name === "@/lib/tank") return {
      tisanGoldPages: async (...args) => { calls.push(args); return [{ tenant_id: args[0] }]; },
      approveTisanGold: async (...args) => { calls.push(args); return { approved: true }; },
    };
    throw new Error("Unexpected dependency");
  }, exported);
  return { exported, calls };
}

test("founder actions derive workspace/platform scope and reject customers", async () => {
  const prior = process.env.TERVORY_ADMIN_USER_IDS;
  process.env.TERVORY_ADMIN_USER_IDS = "founder-user";
  try {
    const { exported, calls } = actions("founder-user");
    const rows = await exported.loadGoldPages();
    assert.deepEqual(rows.map((row) => row.tenant_id), ["00000000-0000-0000-0000-000000000001", "workspace-tenant"]);
    await exported.approveGoldPage("example", "a".repeat(64), "b".repeat(64), "platform");
    assert.equal(calls.at(-1)[0], "00000000-0000-0000-0000-000000000001");
    await exported.approveGoldPage("example", "a".repeat(64), "b".repeat(64), "workspace");
    assert.equal(calls.at(-1)[0], "workspace-tenant");
    await assert.rejects(exported.approveGoldPage("example", "a".repeat(64), "b".repeat(64), "other-tenant"));
    const customer = actions("customer");
    await assert.rejects(customer.exported.loadGoldPages());
    await assert.rejects(customer.exported.approveGoldPage("example", "a".repeat(64), "b".repeat(64), "platform"));
    assert.equal(customer.calls.length, 0);
  } finally {
    if (prior === undefined) delete process.env.TERVORY_ADMIN_USER_IDS;
    else process.env.TERVORY_ADMIN_USER_IDS = prior;
  }
});
