import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  retries: 0,
  use: { baseURL: "http://127.0.0.1:3000" },
  webServer: {
    command: "npm run start",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: false,
    timeout: 120000,
  },
});
