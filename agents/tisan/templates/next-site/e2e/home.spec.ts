import { expect, test } from "@playwright/test";

test("home has a main landmark without invented content", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main")).toBeAttached();
  await expect(page.getByRole("main")).toBeEmpty();
});
