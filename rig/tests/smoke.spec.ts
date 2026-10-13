import { mkdirSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

mkdirSync("docs/screenshots", { recursive: true });

async function ready(page: Page): Promise<void> {
  await page.goto("/demo/index.html");
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await expect(page.getByRole("heading", { name: /find it/i })).toBeVisible();
}

async function shoot(page: Page, name: string): Promise<void> {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
  await page.locator("tervory-rig").screenshot({ path: `docs/screenshots/${name}.png` });
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => {
    const host = document.querySelector("tervory-rig");
    const shell = host?.shadowRoot?.querySelector(".shell") as HTMLElement | null;
    return {
      doc: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      host: host ? host.scrollWidth - host.clientWidth : 0,
      shell: shell ? shell.scrollWidth - shell.clientWidth : 0,
    };
  });
  expect(overflow.doc).toBeLessThanOrEqual(1);
  expect(overflow.host).toBeLessThanOrEqual(1);
  expect(overflow.shell).toBeLessThanOrEqual(1);
}

async function textOfWidget(page: Page): Promise<string> {
  return page.locator("tervory-rig").evaluate((el) => el.shadowRoot?.querySelector(".shell")?.textContent ?? "");
}

test("main path at 1440 and 390", async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await ready(page);
    await shoot(page, `01-search-${width}`);
    await expectNoHorizontalScroll(page);

    await page.getByRole("searchbox").fill("staccato");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Staccato P", exact: true })).toBeVisible();
    await expect(page.getByText("SAMPLE DATA").first()).toBeVisible();
    await shoot(page, `02-results-${width}`);
    await expectNoHorizontalScroll(page);

    await page.locator(".card", { hasText: "Staccato P" }).getByRole("button", { name: "Complete my setup" }).click();
    await expect(page.getByText("R 96 800")).toBeVisible();
    await expect(page.getByText("R 87 700")).toBeVisible();
    await expect(page.getByText("R 89 000")).toBeVisible();
    await expect(page.getByRole("button", { name: "Quote this only" })).toBeVisible();
    const text = await textOfWidget(page);
    expect(text).not.toMatch(/\bVAT\b|\bmargin\b|landed cost/i);
    const parts = await page.locator(".part").allTextContents();
    expect(parts.length).toBeGreaterThan(0);
    for (const part of parts) expect(part).not.toMatch(/R\s?\d/);
    await shoot(page, `03-setup-${width}`);
    await expectNoHorizontalScroll(page);

    if (width === 1440) {
      const featured = page.locator(".setup.featured");
      await featured.getByRole("button", { name: /Swap/ }).first().click();
      await featured.getByRole("button", { name: "Holosun 507C X2" }).click();
      await expect(featured.getByText("R 90 200")).toBeVisible();
      await expect(featured.getByText("R 96 800")).toHaveCount(0);
      await shoot(page, "03-swap-1440");
    }

    await page.getByRole("searchbox").fill("wilson combat edc x9s");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("heading", { name: /not in our feeds yet/i })).toBeVisible();
    await shoot(page, `04-missing-${width}`);
    await expectNoHorizontalScroll(page);

    if (width === 1440) {
      await page.locator("#link-url").fill("https://example.com/wilson");
      await page.locator("#link-note").fill("Please quote this pistol");
      await page.getByRole("button", { name: "Request a quote", exact: true }).click();
      await expect(page.getByText(/Request received/)).toBeVisible();
    }

    await page.getByRole("searchbox").fill("staccato");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await page.locator(".card", { hasText: "Staccato P" }).getByRole("button", { name: "Explore" }).click();
    await expect(page.getByRole("button", { name: /Red dots/i })).toBeVisible();
    await expect(page.getByText("R 96 800")).toBeVisible();
    await shoot(page, `05-explore-${width}`);
    await expectNoHorizontalScroll(page);

    await page.locator("#ask-q").fill("Will this fit a weapon light too?");
    await page.getByRole("button", { name: "Ask" }).click();
    await expect(page.getByText(/12 weapon lights/)).toBeVisible();

    if (width === 1440) {
      await page.getByRole("button", { name: /Request a quote for this setup/ }).click();
      await page.locator("#quote-name").fill("Ada Lovelace");
      await page.locator("#quote-email").fill("ada@example.com");
      await page.getByRole("button", { name: "Send request" }).click();
      await expect(page.getByText(/Request received\. Reference req_/)).toBeVisible();
      await shoot(page, "06-quote-1440");
      await page.getByRole("button", { name: "Close" }).click();
    }

    await page.getByRole("button", { name: "Back" }).click();
    await expect(page.getByRole("heading", { name: /complete your setup/i })).toBeVisible();
    await page.getByRole("searchbox").fill("staccato");
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(page.getByRole("button", { name: /Selected/ })).toBeVisible();
  }
});

test("neutral theme is not the Custom Nation skin", async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    await ready(page);
    await page.getByRole("button", { name: "Neutral" }).click();
    await expect(page.getByRole("heading", { name: /complete the kit/i })).toBeVisible();
    const tokens = await page.locator("tervory-rig").evaluate((el) => ({
      accent: getComputedStyle(el).getPropertyValue("--rig-accent").trim(),
      radius: getComputedStyle(el).getPropertyValue("--rig-radius").trim(),
      font: getComputedStyle(el).getPropertyValue("--rig-font-heading").trim(),
    }));
    expect(tokens.accent).toBe("#1d4e89");
    expect(tokens.radius).toBe("10px");
    expect(tokens.font.toLowerCase()).toContain("newsreader");
    await shoot(page, `neutral-search-${width}`);
    await expectNoHorizontalScroll(page);
    if (width === 1440) {
      await page.getByRole("searchbox").fill("staccato");
      await page.getByRole("button", { name: "Search", exact: true }).click();
      await page.locator(".card", { hasText: "Staccato P" }).getByRole("button", { name: "Complete my setup" }).click();
      await expect(page.getByText("R 96 800")).toBeVisible();
      await shoot(page, "neutral-setup-1440");
      await expectNoHorizontalScroll(page);
    }
  }
});

test("search is keyboard reachable", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await ready(page);
  await page.getByRole("searchbox").focus();
  await page.keyboard.type("staccato");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Staccato C2" })).toBeVisible();
  const complete = page.locator(".card", { hasText: "Staccato P" }).getByRole("button", { name: "Complete my setup" });
  await complete.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(/Complete your setup/i)).toBeVisible();
  const swap = page.locator(".setup.featured").getByRole("button", { name: /^Swap/ }).first();
  await swap.focus();
  await page.keyboard.press("Enter");
  const option = page.locator(".setup.featured").getByRole("button", { name: "Holosun 507C X2" });
  await expect(option).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(option).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".setup.featured").getByText("R 90 200")).toBeVisible();
});
