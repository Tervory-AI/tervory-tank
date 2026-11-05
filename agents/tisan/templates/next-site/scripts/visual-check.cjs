const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const Module = require("node:module");

function checker() {
  const ts = require("typescript");
  const filename = join(__dirname, "../visual/check.ts");
  const compiled = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true },
  }).outputText;
  const loaded = new Module(filename, module);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(join(__dirname, "../visual"));
  loaded._compile(compiled, filename);
  return loaded.exports;
}

async function visualChecks(browser, origin, recorded) {
  const result = { ok: false, frames: [] };
  try {
    const { validateFrames, scoreFrame } = checker();
    const frames = validateFrames(recorded);
    for (const frame of frames) {
      const context = await browser.newContext({
        viewport: { width: frame.width, height: frame.height },
        serviceWorkers: "block",
      });
      try {
        await context.route("**/*", (route) => {
          const request = route.request();
          return new URL(request.url()).origin === origin &&
            ["GET", "HEAD"].includes(request.method())
            ? route.continue()
            : route.abort();
        });
        const page = await context.newPage();
        const response = await page.goto(origin + frame.page, { waitUntil: "networkidle" });
        if (!response || response.status() !== 200) throw new Error("frame data incomplete");
        await page.evaluate(async () => {
          await document.fonts.ready;
          await Promise.all(Array.from(document.images).map((image) => image.decode()));
        });
        await page.addStyleTag({
          content:
            "*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }",
        });
        result.frames.push(await scoreFrame(page, frame));
      } finally {
        await context.close();
      }
    }
    result.ok = result.frames.length === frames.length && result.frames.every((row) => row.passed);
  } catch {
    result.ok = false;
  }
  return result;
}
module.exports = { visualChecks };
