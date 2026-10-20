const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const root = path.resolve(__dirname, "..");
const workspaceRequire = createRequire(path.join(root, "workspace/package.json"));
const ts = workspaceRequire("typescript");
const React = workspaceRequire("react");
const { renderToStaticMarkup } = workspaceRequire("react-dom/server");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE);
const source = fs.readFileSync(path.join(root, "workspace/app/base/context-comparison.tsx"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS },
}).outputText;
const component = { exports: {} };
const reportSource = ts.transpileModule(fs.readFileSync(path.join(root, "workspace/app/base/context-report.ts"), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const reportModule = { exports: {} };
new Function("require", "module", "exports", reportSource)(workspaceRequire, reportModule, reportModule.exports);
const previewRequire = (name) => name === "next/navigation" ? { useRouter: () => ({ refresh() {} }) }
  : name === "./context-report" ? reportModule.exports : workspaceRequire(name);
new Function("require", "module", "exports", compiled)(previewRequire, component, component.exports);
const report = {
  records: 20, creditsUsed: 200, noTruth: 10, creditsPerRecord: 10, unknownCharges: 0, creditCapReached: true,
  fields: [
    { field: "website", checked: 10, baseCorrect: 9, contextCorrect: 8 },
    { field: "phone", checked: 10, baseCorrect: 10, contextCorrect: 0 },
    { field: "address", checked: 10, baseCorrect: 10, contextCorrect: 0 },
  ],
};
const markup = renderToStaticMarkup(React.createElement(component.exports.ContextComparison, { report, canRunTrial: true }));
const css = fs.readFileSync(path.join(root, "workspace/app/base/base.css"), "utf8");
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [375, 1440]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      await page.setContent(`<style>${css}</style><div class="bcp"><main style="padding:24px"><p>Layout preview · synthetic results</p>${markup}</main></div>`);
      await page.screenshot({ path: path.join(root, `tests/fixtures/base-context-${width}.png`), fullPage: true });
      await page.close();
    }
  } finally {
    await browser.close();
  }
})();
