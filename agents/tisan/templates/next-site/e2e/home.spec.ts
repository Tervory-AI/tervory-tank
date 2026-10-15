import { expect, test } from "@playwright/test";

test("home has a main landmark", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main")).toBeVisible();
});
