import { expect, test } from "@playwright/test";

import { sitePaths } from "./site-paths";

for (const path of sitePaths()) {
  test(`${path} shows the main landmark and a heading`, async ({ page }) => {
    const response = await page.goto(path);
    expect(response?.ok()).toBe(true);
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
}

test("the viewport is a required width", async ({ page }) => {
  await page.goto("/");
  expect([390, 768, 1440]).toContain(page.viewportSize()?.width);
});
