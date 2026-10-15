import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "w1-onboarding.spec.ts",
  outputDir: "/tmp/w1-playwright-results",
  timeout: 60_000,
  use: { viewport: { width: 1440, height: 900 } },
});
