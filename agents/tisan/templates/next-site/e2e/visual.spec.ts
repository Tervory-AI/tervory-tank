import { test, expect } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { scoreFrame, validateFrames } from "../visual/check";

const source = "visual/frames.json";
const frames = existsSync(source) ? validateFrames(JSON.parse(readFileSync(source, "utf8"))) : [];

test("Figma comparison requires recorded frame measurements", async () => {
  test.skip(frames.length > 0, "Recorded frames have individual checks below");
  test.skip(true, "UNSCORED: supply visual/frames.json with 375px and 1440px frame measurements");
});

for (const frame of frames) {
  test(`frame ${frame.frameId}: ${frame.page} at ${frame.width}px`, async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "Each frame runs once at its recorded width");
    await page.setViewportSize({ width: frame.width, height: frame.height });
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      return url.origin === "http://127.0.0.1:3000" ? route.continue() : route.abort();
    });
    await page.goto(frame.page);
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all(
        Array.from(document.images).map((image) => image.decode().catch(() => undefined)),
      );
    });
    await page.addStyleTag({
      content:
        "*, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }",
    });
    const report = await scoreFrame(page, frame);
    await info.attach("visual-score", {
      body: JSON.stringify(report, null, 2),
      contentType: "application/json",
    });
    await page.screenshot({ path: info.outputPath(`page-${frame.width}.png`), fullPage: true });
    console.log(JSON.stringify(report));
    expect(report.passed, "Frame regression: see visual-score attachment").toBe(true);
  });
}
