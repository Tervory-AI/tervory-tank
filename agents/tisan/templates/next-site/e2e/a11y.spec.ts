import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { sitePaths } from "./site-paths";

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
}

for (const path of sitePaths()) {
  test(`${path} has no accessibility violations`, async ({ page }) => {
    await page.goto(path);
    await expectNoViolations(page);
  });
}

test("a missing page has no accessibility violations", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expectNoViolations(page);
});
