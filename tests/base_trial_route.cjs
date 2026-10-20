const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const root = path.resolve(__dirname, "..");
const workspaceRequire = createRequire(path.join(root, "workspace/package.json"));
const ts = workspaceRequire("typescript");
const React = workspaceRequire("react");
const { renderToStaticMarkup } = workspaceRequire("react-dom/server");
let userId = null;
let calls = [];
let fail = false;
const mocks = {
  "@clerk/nextjs/server": { auth: async () => ({ userId }) },
  "@/lib/admin": { isFounder: (value) => value === "founder-placeholder" },
  "@/lib/tank": { runContextTrial: async (value) => {
    calls.push(value);
    if (fail) throw new Error("not exposed");
    return { records_sent: 3 };
  } },
  "next/server": { NextResponse: { json: (value, init) => Response.json(value, init) } },
  "next/navigation": { useRouter: () => ({ refresh() {} }) },
};
function load(file) {
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root, file), "utf8"), {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)(
    (name) => mocks[name] ?? workspaceRequire(name), module, module.exports,
  );
  return module.exports;
}
mocks["./context-report"] = load("workspace/app/base/context-report.ts");
(async () => {
  const { POST } = load("workspace/app/api/base/context-trial/route.ts");
  const request = (origin = "https://app.example.com") => new Request("https://app.example.com/api/base/context-trial", {
    method: "POST", headers: { origin, "x-tervory-admin": "forged" },
    body: JSON.stringify({ tenant_id: "client", checked_answers: { website: "forged" } }),
  });
  assert.equal((await POST(request())).status, 404);
  userId = "client-placeholder";
  assert.equal((await POST(request())).status, 404);
  userId = "founder-placeholder";
  assert.equal((await POST(request("https://other.example.com"))).status, 403);
  assert.deepEqual(calls, []);
  assert.deepEqual(await (await POST(request())).json(), { records_sent: 3 });
  assert.deepEqual(calls, ["founder-placeholder"]);
  fail = true;
  const failed = await POST(request());
  assert.equal(failed.status, 503);
  assert.ok(!(await failed.text()).includes("not exposed"));
  const { ContextComparison } = load("workspace/app/base/context-comparison.tsx");
  const report = { records: 2, creditsUsed: 20, noTruth: 2, creditsPerRecord: 10, unknownCharges: 0, fields: [] };
  const client = renderToStaticMarkup(React.createElement(ContextComparison, { report }));
  assert.ok(!client.includes("Run Context.dev trial"));
  const founder = renderToStaticMarkup(React.createElement(ContextComparison, { report, canRunTrial: true }));
  assert.ok(founder.includes("Run Context.dev trial"));
  assert.ok(founder.includes("no truth yet"));
  assert.ok(founder.includes("Credits used: 20.00"));
})().catch((error) => { console.error(error); process.exitCode = 1; });
