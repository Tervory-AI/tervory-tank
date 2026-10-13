import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests",
  testMatch: "*.spec.ts",
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
  },
  webServer: {
    command: "npx vite --host 127.0.0.1 --port 5173",
    url: "http://127.0.0.1:5173/demo/index.html",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
