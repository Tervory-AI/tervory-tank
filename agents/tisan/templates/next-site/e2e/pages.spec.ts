import { expect, test } from "@playwright/test";

import { sitePaths } from "./site-paths";

for (const path of sitePaths()) {
  test(`${path} has its existing page or an empty pending design`, async ({ page }, info) => {
    const response = await page.goto(path);
    expect(response?.ok()).toBe(true);
    await expect(page.getByRole("main")).toBeAttached();
    if (["/contact", "/privacy"].includes(path)) {
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    } else {
      await expect(page.getByRole("main")).toBeEmpty();
    }
    await info.attach("page", {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    });
  });
}

test("the viewport is a required width", async ({ page }) => {
  await page.goto("/");
  expect([390, 768, 1440]).toContain(page.viewportSize()?.width);
});
