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
    if (fail) throw fail instanceof Error ? fail : new Error("not exposed");
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
mocks["@/app/base/context-trial-error"] = load("workspace/app/base/context-trial-error.ts");
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
  for (const message of [
    "No completed batch to test yet. Run a Base batch first.",
    "A trial is already running (started 09:07).",
  ]) {
    fail = new Error(`Tank /v1/base/context-dev/trial 409: ${JSON.stringify({ detail: message })}`);
    const response = await POST(request());
    assert.equal(response.status, 409);
    const result = await response.json();
    assert.deepEqual(result, { error: message });
    const state = [];
    let index = 0;
    mocks.react = { ...React, useState: (initial) => {
      const slot = index++;
      if (!(slot in state)) state[slot] = initial;
      return [state[slot], (next) => { state[slot] = next; }];
    } };
    const Component = load("workspace/app/base/context-comparison.tsx").ContextComparison;
    const props = { report: { records: 0, fields: [] }, canRunTrial: true };
    const section = Component(props);
    const button = section.props.children.find(child => child?.type === "button");
    global.fetch = async () => ({ ok: false, json: async () => result });
    await button.props.onClick();
    index = 0;
    const markup = renderToStaticMarkup(Component(props));
    assert.ok(markup.includes(message));
    assert.ok(markup.includes('role="status"'));
    assert.equal(markup.includes("Start time is UTC."), message.startsWith("A trial"));
    if (process.env.BASE_TRIAL_PREVIEW_DIR) {
      fs.mkdirSync(process.env.BASE_TRIAL_PREVIEW_DIR, { recursive: true });
      fs.writeFileSync(path.join(process.env.BASE_TRIAL_PREVIEW_DIR, message.startsWith("A trial") ? "running.html" : "no-batch.html"), markup);
    }
    delete mocks.react;
  }
  for (const error of [
    new Error('Tank /v1/base/context-dev/trial 409: {"detail":"private error"}'),
    new Error('Tank /v1/base/context-dev/trial 409: malformed'),
    new Error('Tank /v1/base/context-dev/trial 503: {"detail":"A trial is already running (started 09:07)."}'),
  ]) {
    fail = error;
    const response = await POST(request());
    assert.equal(response.status, 503);
    assert.deepEqual(await response.json(), { error: "Trial interrupted. Refresh results before trying again." });
  }
  const { ContextComparison } = load("workspace/app/base/context-comparison.tsx");
  const report = { records: 2, creditsUsed: 20, noTruth: 2, creditsPerRecord: 10, unknownCharges: 0, fields: [] };
  const client = renderToStaticMarkup(React.createElement(ContextComparison, { report }));
  assert.ok(!client.includes("Run Context.dev trial"));
  const founder = renderToStaticMarkup(React.createElement(ContextComparison, { report, canRunTrial: true }));
  assert.ok(founder.includes("Run Context.dev trial"));
  assert.ok(founder.includes("no truth yet"));
  assert.ok(founder.includes("Credits used: 20.00"));
  mocks.react = {
    ...React,
    useState: (initial) => React.useState(initial === null ? {
      records: 0, creditsUsed: 0, noTruth: 0, creditsPerRecord: null,
      unknownCharges: 0, creditCapReached: true, fields: [],
    } : initial),
  };
  const cappedComponent = load("workspace/app/base/context-comparison.tsx").ContextComparison;
  const capped = renderToStaticMarkup(React.createElement(cappedComponent, { report, canRunTrial: true }));
  assert.ok(capped.includes("This press: records sent: 0"));
  assert.ok(capped.includes("Credits used: 0.00"));
  assert.ok(capped.includes("credit cap reached"));
  assert.ok(!capped.includes("No trial results yet"));
})().catch((error) => { console.error(error); process.exitCode = 1; });
