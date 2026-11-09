const { chromium } = require("@playwright/test");

const { sitePaths } = require("./scripts/site-paths.cjs");

const categories = ["performance", "accessibility", "best-practices", "seo"];
const assertions = {
  "categories:performance": ["error", { minScore: 0.9 }],
  "categories:accessibility": ["error", { minScore: 0.95 }],
  "categories:best-practices": ["error", { minScore: 0.9 }],
  "categories:seo": ["error", { minScore: 0.9 }],
};

const origin = process.env.TISAN_CHECK_ORIGIN || "http://127.0.0.1:3000";
const pages = process.env.TISAN_CHECK_PAGES
  ? JSON.parse(process.env.TISAN_CHECK_PAGES)
  : sitePaths();

module.exports = {
  ci: {
    collect: {
      url: pages.map((path) => `${origin}${path}`),
      startServerCommand: process.env.TISAN_CHECK_ORIGIN
        ? undefined
        : "npx next start -H 127.0.0.1 -p 3000",
      startServerReadyPattern: "Ready",
      startServerReadyTimeout: 120000,
      numberOfRuns: 3,
      chromePath: chromium.executablePath(),
      settings: {
        ...(process.env.TISAN_CHECK_CHROME_PORT
          ? { port: Number(process.env.TISAN_CHECK_CHROME_PORT) }
          : {}),
        chromeFlags:
          "--no-sandbox --disable-dev-shm-usage --disable-gpu --disable-background-networking" +
          (process.env.TISAN_CHECK_PROXY
            ? ` --proxy-server=${process.env.TISAN_CHECK_PROXY} --proxy-bypass-list=<-loopback> --host-resolver-rules="MAP * ~NOTFOUND, EXCLUDE 127.0.0.1"`
            : ""),
        formFactor: "mobile",
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
