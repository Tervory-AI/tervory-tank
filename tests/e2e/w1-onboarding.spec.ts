import { expect, test, type Page } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { createServer, type Server } from "node:http";
import { readFileSync } from "node:fs";
import path from "node:path";

const root = path.resolve(__dirname, "../..");
const fixture = path.join(root, "tests/e2e/fixtures/clients.csv");
const bundle = "/tmp/w1-harness.js";
const shots = "/opt/cursor/artifacts";

let server: Server;
let base: string;

async function walkToFile(page: Page) {
  await page.goto(base);
  await page.getByLabel("Email").fill("ada@northharbor.example");
  await page.getByLabel("Password").fill("correct horse");
  await page.getByRole("button", { name: "Sign up" }).click();
  await page.getByLabel("Organization name").fill("North Harbor");
  await page.getByRole("button", { name: "Create organization" }).click();
  await expect(page.getByText("You are in North Harbor.")).toBeVisible();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.getByRole("radio", { name: /Firearms dealers/ }).check();
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("button", { name: "Start" })).toBeDisabled();
  await expect(page.locator("[data-uploads]")).toHaveAttribute("data-uploads", "0");
}

test.beforeAll(() => {
  const esbuild = process.env.ESBUILD || "esbuild";
  const built = spawnSync(esbuild, [
    path.join(root, "tests/e2e/harness.tsx"),
    "--bundle",
    "--format=esm",
    `--outfile=${bundle}`,
    "--jsx=automatic",
    `--alias:react=${path.join(root, "workspace/node_modules/react")}`,
    `--alias:react-dom/client=${path.join(root, "workspace/node_modules/react-dom/client")}`,
    `--alias:react/jsx-runtime=${path.join(root, "workspace/node_modules/react/jsx-runtime")}`,
  ], { encoding: "utf8" });
  if (built.status !== 0) throw new Error(built.stderr || built.stdout || "esbuild failed");

  server = createServer((req, res) => {
    const url = new URL(req.url || "/", "http://127.0.0.1");
    if (url.pathname === "/harness.js") {
      res.setHeader("content-type", "text/javascript");
      res.end(readFileSync(bundle));
      return;
    }
    if (url.pathname === "/onboarding.css") {
      res.setHeader("content-type", "text/css");
      res.end(readFileSync(path.join(root, "workspace/app/onboarding/onboarding.css")));
      return;
    }
    if (url.pathname === "/brand/tervory-logo.png") {
      res.setHeader("content-type", "image/png");
      res.end(readFileSync(path.join(root, "workspace/public/brand/tervory-logo.png")));
      return;
    }
    if (url.pathname === "/data") {
      const batch = url.searchParams.get("batch") || "";
      res.setHeader("content-type", "text/html; charset=utf-8");
      res.end(`<!doctype html><html><head><title>Data</title></head><body><h1>Data</h1><p>Showing batch ${batch}</p></body></html>`);
      return;
    }
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end(`<!doctype html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <link rel="stylesheet" href="/onboarding.css" />
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400&family=Jost:wght@300&display=swap" />
  <style>.onboard{--onb-body:"Inter";--onb-heading:"Jost";--onb-mono:"JetBrains Mono";}</style>
</head>
<body>
  <main style="max-width:820px;margin:0 auto;padding:24px 16px 120px">
    <div id="root" class="onboard"></div>
  </main>
  <script type="module" src="/harness.js"></script>
</body>
</html>`);
  });
  return new Promise<void>((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const addr = server.address();
      const port = typeof addr === "object" && addr ? addr.port : 0;
      base = `http://127.0.0.1:${port}/`;
      resolve();
    });
  });
});

test.afterAll(() => new Promise<void>((resolve) => server.close(() => resolve())));

test("a fresh organization goes from sign-up to a started batch", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await walkToFile(page);
  const csv = readFileSync(fixture, "utf8");
  await page.locator(".drop").evaluate((el, text) => {
    const file = new File([text], "clients.csv", { type: "text/csv" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    el.dispatchEvent(new DragEvent("drop", { bubbles: true, dataTransfer: transfer }));
  }, csv);
  await expect(page.getByText("Showing the first 5 of 6 rows.")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Acme Guns" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Bay Tools" })).toHaveCount(0);
  await expect(page.getByText("Nothing waits for approval.")).toBeVisible();
  await expect(page.getByText("6 records will be uploaded when you press Start.")).toBeVisible();
  await expect(page.locator("[data-uploads]")).toHaveAttribute("data-uploads", "0");
  await page.screenshot({ path: path.join(shots, "w1-file-1440.png"), fullPage: true });
  await page.getByRole("button", { name: "Start" }).click();
  await expect(page.locator("[data-uploads]")).toHaveAttribute("data-uploads", "1");
  await expect(page.getByRole("heading", { name: "Your run has started" })).toBeVisible();
  await expect(page.getByText("Clean names and addresses")).toBeVisible();
  await expect(page.getByText("1 of 6")).toBeVisible();
  await page.screenshot({ path: path.join(shots, "w1-run-1440.png"), fullPage: true });
  await page.getByRole("link", { name: "See your records" }).click();
  await expect(page).toHaveURL(/\/data\?batch=clients$/);
  await expect(page.getByRole("heading", { name: "Data" })).toBeVisible();
  await expect(page.getByText("Showing batch clients")).toBeVisible();
});

test("the file step fits a phone width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await walkToFile(page);
  await page.setInputFiles("input[type=file]", fixture);
  await expect(page.getByRole("button", { name: "Start" })).toBeEnabled();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
  expect(overflow).toBe(false);
  await page.screenshot({ path: path.join(shots, "w1-file-390.png"), fullPage: true });
});

test("a file with no name column cannot start", async ({ page }) => {
  await walkToFile(page);
  await page.setInputFiles("input[type=file]", {
    name: "places.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("city,state\nBoston,MA\n"),
  });
  await expect(page.getByText("Choose which column is the business name.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start" })).toBeDisabled();
  await expect(page.locator("[data-uploads]")).toHaveAttribute("data-uploads", "0");
});
