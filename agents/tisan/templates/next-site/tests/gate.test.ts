import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

import { expect, test } from "vitest";

import { sitePaths } from "../e2e/site-paths";

const { sitePaths: lighthousePaths } = createRequire(import.meta.url)(
  "../scripts/site-paths.cjs",
) as { sitePaths: () => string[] };

test("linked pages are paths from the site file", () => {
  const paths = sitePaths();
  expect(paths.length).toBeGreaterThan(0);
  expect(paths[0]).toBe("/");
  for (const path of paths) {
    expect(path.startsWith("/")).toBe(true);
  }
  expect(lighthousePaths()).toEqual(paths);
});

test("the GitHub Actions gate requires a full pass", () => {
  const workflow = readFileSync(".github/workflows/ci.yml", "utf8");
  for (const command of [
    "npm run lint",
    "npm run typecheck",
    "npm test",
    "npm run build",
    "npm run deploy",
    "npm run test:e2e",
    "npm run lhci",
  ]) {
    expect(workflow).toContain(command);
  }
  expect(workflow.indexOf("npm run deploy")).toBeGreaterThan(workflow.indexOf("npm run build"));

  const lighthouse = readFileSync("lighthouserc.cjs", "utf8");
  for (const category of ["performance", "accessibility", "best-practices", "seo"]) {
    expect(lighthouse).toContain(`categories:${category}`);
  }
  expect(lighthouse).toContain("minScore: 0.9");
  expect(lighthouse).toContain("numberOfRuns: 3");

  const playwright = readFileSync("playwright.config.ts", "utf8");
  expect(playwright).toContain("width: 390");
  expect(playwright).toContain("width: 768");
  expect(playwright).toContain("width: 1440");

  const axe = readFileSync("e2e/a11y.spec.ts", "utf8");
  expect(axe).toContain("@axe-core/playwright");
});
