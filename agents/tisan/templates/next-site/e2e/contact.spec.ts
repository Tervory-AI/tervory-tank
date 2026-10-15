import { expect, test } from "@playwright/test";

test("contact form is labelled", async ({ page }) => {
  await page.goto("/contact");
  await expect(page.getByLabel("Name")).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Message")).toBeVisible();
});
