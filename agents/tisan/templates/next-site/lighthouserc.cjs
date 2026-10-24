const { chromium } = require("@playwright/test");

const { sitePaths } = require("./scripts/site-paths.cjs");

const categories = ["performance", "accessibility", "best-practices", "seo"];
const assertions = {
  "categories:performance": ["error", { minScore: 0.9 }],
  "categories:accessibility": ["error", { minScore: 0.9 }],
  "categories:best-practices": ["error", { minScore: 0.9 }],
  "categories:seo": ["error", { minScore: 0.9 }],
};

const origin = "http://127.0.0.1:3000";

module.exports = {
  ci: {
    collect: {
      url: sitePaths().map((path) => `${origin}${path}`),
      startServerCommand: "npx next start -H 127.0.0.1 -p 3000",
      startServerReadyPattern: "Ready",
      startServerReadyTimeout: 120000,
      numberOfRuns: 3,
      chromePath: process.env.CHROME_PATH || chromium.executablePath(),
      settings: {
        chromeFlags: "--no-sandbox --disable-dev-shm-usage --disable-gpu",
        onlyCategories: categories,
      },
    },
    assert: { assertions },
    upload: {
      target: "filesystem",
      outputDir: ".lighthouseci",
    },
  },
};
