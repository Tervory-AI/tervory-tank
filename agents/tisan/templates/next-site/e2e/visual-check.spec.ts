import { test, expect } from "@playwright/test";
import { scoreFrame, validateFrames, type Frame } from "../visual/check";

// Synthetic browser truth exercises the checker; not a founder-approved Figma page.
for (const width of [375, 1440] as const) {
  test(`visual checker detects independent regressions at ${width}px`, async ({ page }, info) => {
    test.skip(info.project.name !== "desktop", "Run each requested width once");
    await page.setViewportSize({ width, height: 900 });
    await page.setContent(
      `<style>:root{--ink:#001840}body{margin:0}h1{position:absolute;left:16px;top:32px;width:200px;height:40px;margin:0;color:var(--ink)}</style><h1>Example</h1>`,
    );
    const frame: Frame = {
      page: "/",
      frameId: "synthetic",
      width,
      height: 900,
      tokens: { "--ink": "#001840" },
      elements: [
        {
          nodeId: "heading",
          selector: "h1",
          box: { x: 16, y: 32, width: 200, height: 40 },
          text: "Example",
          colours: { color: "--ink" },
        },
      ],
    };
    expect((await scoreFrame(page, frame)).passed).toBe(true);
    await expect(scoreFrame(page, { ...frame, elements: [] })).rejects.toThrow(
      "frame data incomplete",
    );
    await page
      .locator("h1")
      .evaluate((node) => (node as HTMLElement).style.setProperty("--ink", "#ff0000"));
    expect((await scoreFrame(page, frame)).scores.colour).toBe(0);
    await page.locator("h1").evaluate((node) => node.removeAttribute("style"));
    await page.locator("h1").evaluate((node) => ((node as HTMLElement).style.opacity = "0"));
    expect((await scoreFrame(page, frame)).passed).toBe(false);
    await page.locator("h1").evaluate((node) => node.removeAttribute("style"));
    for (const [property, value, kind] of [
      ["left", "30px", "layout"],
      ["color", "red", "colour"],
    ]) {
      await page
        .locator("h1")
        .evaluate(
          (node, change) => (node as HTMLElement).style.setProperty(change[0], change[1]),
          [property, value],
        );
      const report = await scoreFrame(page, frame);
      expect(report.passed).toBe(false);
      expect(report.scores[kind]).toBe(0);
      await page.locator("h1").evaluate((node) => node.removeAttribute("style"));
    }
    await page.locator("h1").evaluate((node) => {
      node.textContent = "Changed";
    });
    expect((await scoreFrame(page, frame)).scores.text).toBe(0);
    await page.locator("h1").evaluate((node) => {
      node.remove();
    });
    expect((await scoreFrame(page, frame)).score).toBe(0);
  });
}

test("incomplete or mismatched viewport evidence is rejected", () => {
  expect(() => validateFrames([])).toThrow();
  expect(() => validateFrames([{ width: 390 }])).toThrow();
});
