/* Offline browser checks for generated sites. No provider or model clients. */
const http = require("node:http");
const { spawn } = require("node:child_process");
const {
  readFileSync,
  readdirSync,
  existsSync,
  rmSync,
  mkdirSync,
  writeFileSync,
} = require("node:fs");
const { join } = require("node:path");
const { chromium } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;
const { sitePaths } = require("./site-paths.cjs");

const listen = (server) =>
  new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
const close = (server) =>
  new Promise((resolve) => {
    server.closeAllConnections();
    server.close(resolve);
  });
const local = (url, origin) => {
  try {
    return new URL(url, origin).origin === origin;
  } catch {
    return false;
  }
};

function pages(root = process.cwd()) {
  const paths = sitePaths();
  const manifest = join(root, ".next/server/app-paths-manifest.json");
  if (existsSync(manifest))
    for (const key of Object.keys(JSON.parse(readFileSync(manifest, "utf8")))) {
      if (
        !key.endsWith("/page") ||
        key.includes("[") ||
        key.startsWith("/_") ||
        key.startsWith("/api/")
      )
        continue;
      paths.push(key.slice(0, -5) || "/");
    }
  return [...new Set(paths)];
}

// Browser traffic goes through this allowlist, including Lighthouse's Chromium.
// CONNECT, off-origin redirects, WebSockets and external HTTP are never forwarded.
function proxyFor(origin) {
  const proxy = http.createServer((req, res) => {
    if (!local(req.url, origin)) {
      res.writeHead(403);
      res.end();
      return;
    }
    // Host and port come only from the fixed local origin; the request supplies the path.
    const fixed = new URL(origin);
    const { pathname, search } = new URL(req.url, origin);
    const upstream = http.request(
      {
        protocol: fixed.protocol,
        hostname: fixed.hostname,
        port: fixed.port,
        path: pathname + search,
        method: req.method,
        headers: { ...req.headers, host: fixed.host },
      },
      (response) => {
        res.writeHead(response.statusCode, response.headers);
        response.pipe(res);
      },
    );
    upstream.on("error", () => {
      res.writeHead(502);
      res.end();
    });
    req.pipe(upstream);
  });
  proxy.on("connect", (_req, socket) => socket.destroy());
  proxy.on("upgrade", (_req, socket) => socket.destroy());
  return proxy;
}

function lighthouseScores(reports, assertions) {
  const scores = [],
    failures = [];
  for (const url of [...new Set(reports.map((r) => r.requestedUrl))]) {
    const runs = reports.filter((r) => r.requestedUrl === url);
    const medians = {};
    for (const [key, assertion] of Object.entries(assertions)) {
      const category = key.replace("categories:", "");
      const values = runs
        .map((r) => r.categories?.[category]?.score)
        .filter((v) => typeof v === "number")
        .sort((a, b) => a - b);
      const value = values.length === runs.length ? values[Math.floor(values.length / 2)] : null;
      medians[category] = value;
      if (value === null || value < assertion[1].minScore)
        failures.push({
          page: new URL(url).pathname,
          category,
          score: value,
          threshold: assertion[1].minScore,
        });
    }
    scores.push({
      page: new URL(url).pathname,
      scores: medians,
      runs: runs.map((r) =>
        Object.fromEntries(Object.entries(r.categories || {}).map(([k, v]) => [k, v.score])),
      ),
    });
  }
  return { scores, failures };
}

async function browserChecks(origin, paths, proxyUrl) {
  const accessibility = { name: "accessibility", ok: true, pages: [], violations: [] };
  const links = { name: "links", ok: true, checked: [], failures: [], external: [] };
  const browser = await chromium.launch({
    proxy: { server: proxyUrl, bypass: "<-loopback>" },
    args: [
      "--disable-background-networking",
      "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    ],
  });
  try {
    for (const width of [390, 1440]) {
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        serviceWorkers: "block",
      });
      await context.route("**/*", (route) =>
        local(route.request().url(), origin) ? route.continue() : route.abort(),
      );
      try {
        for (const path of paths) {
          const page = await context.newPage();
          const resources = new Set();
          page.on("request", (req) => resources.add(req.url()));
          try {
            const response = await page.goto(origin + path, {
              waitUntil: "networkidle",
              timeout: 30000,
            });
            if (response.status() !== 200) throw new Error("page did not answer 200");
            const axe = await new AxeBuilder({ page }).analyze();
            const violations = axe.violations
              .filter((v) => ["serious", "critical"].includes(v.impact))
              .flatMap((v) =>
                v.nodes.map((n) => ({
                  page: path,
                  width,
                  rule: v.id,
                  impact: v.impact,
                  element: n.target.join(" "),
                })),
              );
            accessibility.pages.push({ page: path, width, violations });
            accessibility.violations.push(...violations);
            const refs = await page
              .locator(
                "a[href],area[href],link[href],img[src],script[src],source[src],video[src],audio[src],video[poster]",
              )
              .evaluateAll((nodes) =>
                nodes.map((n) => n.href || n.src || n.poster).filter(Boolean),
              );
            refs.forEach((url) => resources.add(url));
            const srcsets = await page
              .locator("img[srcset],source[srcset]")
              .evaluateAll((nodes) =>
                nodes.flatMap((n) => n.srcset.split(",").map((s) => s.trim().split(/\s+/)[0])),
              );
            srcsets.forEach((url) => resources.add(new URL(url, page.url()).href));
            for (const ref of resources) {
              const url = new URL(ref, origin);
              if (!["http:", "https:"].includes(url.protocol)) continue;
              if (!local(url.href, origin)) {
                links.external.push({ page: path, url: url.href });
                continue;
              }
              url.hash = "";
              if (links.checked.some((r) => r.page === path && r.url === url.pathname + url.search))
                continue;
              let status = 0;
              try {
                const answer = await fetch(url.href, {
                  redirect: "manual",
                  signal: AbortSignal.timeout(10000),
                });
                status = answer.status;
                if ((answer.headers.get("content-type") || "").includes("text/css")) {
                  const css = await answer.text();
                  const refs = [
                    ...css.matchAll(/url\(\s*(?:"([^"]+)"|'([^']+)'|([^\s)]+))\s*\)/g),
                  ].map((m) => m[1] || m[2] || m[3]);
                  refs.push(...[...css.matchAll(/@import\s+["']([^"']+)["']/g)].map((m) => m[1]));
                  refs.forEach((ref) => resources.add(new URL(ref, url.href).href));
                } else await answer.body?.cancel();
              } catch {
                /* status 0 fails closed */
              }
              const result = { page: path, url: url.pathname + url.search, status };
              links.checked.push(result);
              if (status !== 200) links.failures.push(result);
            }
          } catch {
            accessibility.violations.push({
              page: path,
              width,
              rule: "page-check-unavailable",
              element: "document",
            });
            links.failures.push({ page: path, url: path, status: 0 });
          } finally {
            await page.close();
          }
        }
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  accessibility.ok = accessibility.violations.length === 0;
  links.ok = links.failures.length === 0;
  return [accessibility, links];
}

async function lighthouse(origin, paths, proxyUrl) {
  const reportDir = join(process.cwd(), ".lighthouseci");
  rmSync(reportDir, { recursive: true, force: true });
  const env = {
    ...process.env,
    TISAN_CHECK_ORIGIN: origin,
    TISAN_CHECK_PROXY: proxyUrl,
    TISAN_CHECK_PAGES: JSON.stringify(paths),
    NPM_CONFIG_OFFLINE: "true",
  };
  let runnerLog = "";
  const code = await new Promise((resolve) => {
    const child = spawn("npm", ["run", "lhci"], { env, stdio: ["ignore", "pipe", "pipe"] });
    const collect = (chunk) => {
      runnerLog = (runnerLog + chunk.toString()).slice(-100000);
    };
    child.stdout.on("data", collect);
    child.stderr.on("data", collect);
    child.on("error", () => resolve(127));
    child.on("exit", (code) => resolve(code));
  });
  mkdirSync(reportDir, { recursive: true });
  writeFileSync(join(reportDir, "runner.log"), runnerLog);
  const reports = existsSync(reportDir)
    ? readdirSync(reportDir)
        .filter((n) => /^lhr-.*\.json$/.test(n))
        .map((n) => JSON.parse(readFileSync(join(reportDir, n), "utf8")))
    : [];
  const config = require("../lighthouserc.cjs");
  const detail = lighthouseScores(reports, config.ci.assert.assertions);
  const seen = new Set(detail.scores.map((r) => r.page));
  const missing = paths.filter((path) => !seen.has(path));
  return {
    name: "lighthouse",
    ok: code === 0 && reports.length > 0 && !detail.failures.length && !missing.length,
    ...detail,
    missing,
  };
}

async function run() {
  const paths = pages();
  if (!paths.length) throw new Error("no pages to check");
  const reserved = http.createServer();
  const port = await listen(reserved);
  await close(reserved);
  const origin = `http://127.0.0.1:${port}`;
  const proxy = proxyFor(origin);
  const proxyPort = await listen(proxy);
  const proxyUrl = `http://127.0.0.1:${proxyPort}`;
  process.env.TISAN_CHECK_ORIGIN = origin;
  process.env.TISAN_CHECK_PROXY = proxyUrl;
  process.env.TISAN_CHECK_PAGES = JSON.stringify(paths);
  const server = spawn(
    process.execPath,
    [require.resolve("next/dist/bin/next"), "start", "-H", "127.0.0.1", "-p", String(port)],
    { stdio: "ignore" },
  );
  server.on("error", () => {});
  let report;
  try {
    for (let i = 0; i < 100; i++) {
      try {
        const response = await fetch(origin + paths[0], { redirect: "manual" });
        await response.body?.cancel();
        break;
      } catch {
        if (server.exitCode !== null || i === 99) throw new Error("local server unavailable");
        await new Promise((r) => setTimeout(r, 100));
      }
    }
    const [accessibility, links] = await browserChecks(origin, paths, proxyUrl);
    const lh = await lighthouse(origin, paths, proxyUrl);
    report = [accessibility, lh, links];
  } finally {
    server.kill("SIGTERM");
    if (server.exitCode === null)
      await new Promise((resolve) => {
        server.once("exit", resolve);
        setTimeout(() => {
          server.kill("SIGKILL");
          resolve();
        }, 3000).unref();
      });
    await close(proxy);
  }
  return report;
}
if (require.main === module)
  run()
    .then((checks) => {
      writeFileSync(".quality-checks.json", JSON.stringify(checks, null, 2));
      process.exitCode = checks.every((c) => c.ok) ? 0 : 1;
    })
    .catch(() => {
      console.error("local quality checks unavailable");
      process.exitCode = 1;
    });
module.exports = { pages, proxyFor, lighthouseScores, browserChecks, lighthouse, run };
