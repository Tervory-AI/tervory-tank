// Compare disposable copies of the already-deployed site and the candidate image.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const manifest = JSON.parse(await readFile(new URL("../../site/public/fonts/manifest.json", import.meta.url)));
const output = process.env.FONT_PROOF_OUTPUT || "/tmp/site-font-parity";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH, headless: true });
const report = { viewports: [], assets: [] };
try {
  for (const width of [1440, 375]) {
    const captures = [];
    for (const [name, url] of [["before", "http://127.0.0.1:18471"], ["after", "http://127.0.0.1:18472"]]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      const response = await page.goto(url, { waitUntil: "networkidle" });
      assert.equal(response.status(), 200);
      await page.evaluate(() => document.fonts.ready);
      await page.addStyleTag({ content: "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}" });
      const snapshot = await page.evaluate(async () => {
        const elements = [...document.body.querySelectorAll("*")].filter(el => el.getBoundingClientRect().width && el.getBoundingClientRect().height);
        const geometry = elements.map(el => {
          const r = el.getBoundingClientRect(), s = getComputedStyle(el);
          return { tag: el.tagName, text: el.children.length ? "" : el.textContent,
            rect: [r.x, r.y, r.width, r.height], family: s.fontFamily, weight: s.fontWeight,
            size: s.fontSize, style: s.fontStyle, lineHeight: s.lineHeight,
            letterSpacing: s.letterSpacing, variation: s.fontVariationSettings };
        });
        const glyphs = [];
        const sample = "Tervory AI 0123456789 € £ — é Ελληνικά Кириллица";
        for (const [family, weights] of [["Jost", [300, 400]], ["Inter", [400, 500, 600]], ["JetBrains Mono", [400]]]) {
          for (const weight of weights) {
            const font = `${weight} 32px "${family}"`;
            await document.fonts.load(font, sample);
            const context = document.createElement("canvas").getContext("2d");
            context.font = font;
            const m = context.measureText(sample);
            glyphs.push({ family, weight, width: m.width, ascent: m.actualBoundingBoxAscent, descent: m.actualBoundingBoxDescent });
          }
        }
        return { geometry, glyphs, scrollWidth: document.documentElement.scrollWidth };
      });
      const screenshot = await page.screenshot({ fullPage: true, animations: "disabled" });
      await writeFile(`${output}/${width}-${name}.png`, screenshot);
      assert.deepEqual(errors, []);
      captures.push({ snapshot, screenshot });
      await page.close();
    }
    assert.deepEqual(captures[1].snapshot, captures[0].snapshot, `font metrics and geometry at ${width}`);
    assert.ok(captures[0].screenshot.equals(captures[1].screenshot), `pixel parity at ${width}`);
    report.viewports.push({ width, identicalGeometryAndFontMetrics: true, identicalPixels: true,
      sha256: createHash("sha256").update(captures[0].screenshot).digest("hex"),
      snapshot: captures[0].snapshot });
  }
  for (const [name, digest] of Object.entries(manifest.assets_sha256)) {
    const response = await fetch(`http://127.0.0.1:18472/fonts/${name}`);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("content-type"), "font/woff2");
    assert.equal(createHash("sha256").update(Buffer.from(await response.arrayBuffer())).digest("hex"), digest);
    report.assets.push({ name, status: response.status, contentType: response.headers.get("content-type"),
      cacheControl: response.headers.get("cache-control"), sha256: digest });
  }
  await writeFile(`${output}/browser-parity.json`, JSON.stringify(report, null, 2) + "\n");
  console.log("PASS: 1440/375 pixel, geometry, font and glyph metrics; 16 exact font assets HTTP 200.");
} finally {
  await browser.close();
}
