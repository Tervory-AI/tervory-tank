/* Explicit local fixture proof. Never imported by a generated page. */
const assert = require("node:assert/strict");
const http = require("node:http");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { browserChecks, proxyFor, lighthouse } = require("../scripts/quality-check.cjs");
const listen = (s) =>
  new Promise((resolve) => s.listen(0, "127.0.0.1", () => resolve(s.address().port)));
const close = (s) =>
  new Promise((resolve) => {
    s.close(resolve);
    s.closeAllConnections();
  });

async function proof(includeLighthouse = false) {
  const files = {
    "/clean": "quality-clean.html",
    "/missing-alt": "quality-missing-alt.html",
    "/broken": "quality-broken-link.html",
    "/slow": "quality-slow.html",
    "/ok": "quality-clean.html",
  };
  let forbiddenHits = 0;
  const forbidden = http.createServer((_req, res) => {
    forbiddenHits++;
    res.end("should never be fetched");
  });
  const forbiddenPort = await listen(forbidden);
  const server = http.createServer((req, res) => {
    if (req.url === "/ok.svg") {
      res.setHeader("Content-Type", "image/svg+xml");
      res.end('<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"></svg>');
      return;
    }
    if (files[req.url]) {
      res.setHeader("Content-Type", "text/html");
      res.end(readFileSync(join(__dirname, "fixtures", files[req.url]), "utf8"));
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  const port = await listen(server);
  const origin = `http://127.0.0.1:${port}`;
  const proxy = proxyFor(origin),
    proxyPort = await listen(proxy);
  const proxyUrl = `http://127.0.0.1:${proxyPort}`;
  try {
    const blocked = await fetch(proxyUrl, { headers: { host: `127.0.0.1:${forbiddenPort}` } });
    // An absolute off-origin proxy URL must be rejected without contacting it.
    const status = await new Promise((resolve, reject) => {
      const req = http.get(
        { hostname: "127.0.0.1", port: proxyPort, path: `http://127.0.0.1:${forbiddenPort}/` },
        (res) => {
          res.resume();
          resolve(res.statusCode);
        },
      );
      req.on("error", reject);
    });
    await blocked.body?.cancel();
    assert.equal(status, 403);
    assert.equal(forbiddenHits, 0);
    const [accessibility, links] = await browserChecks(
      origin,
      ["/clean", "/missing-alt", "/broken"],
      proxyUrl,
    );
    assert.equal(accessibility.pages.filter((p) => p.page === "/clean").length, 2);
    assert(
      accessibility.pages
        .filter((p) => p.page === "/clean")
        .every((p) => p.violations.length === 0),
    );
    assert(
      accessibility.violations.some(
        (v) => v.page === "/missing-alt" && v.rule === "image-alt" && v.element,
      ),
    );
    assert(
      links.failures.some(
        (v) => v.page === "/broken" && v.url === "/missing-test-link" && v.status === 404,
      ),
    );
    assert(!links.failures.some((v) => v.page === "/clean"));
    assert(links.external.some((v) => v.url === "http://external.invalid/never-fetch"));
    let budget;
    if (includeLighthouse) {
      process.env.TISAN_CHECK_ORIGIN = origin;
      process.env.TISAN_CHECK_PROXY = proxyUrl;
      process.env.TISAN_CHECK_PAGES = JSON.stringify(["/slow"]);
      budget = await lighthouse(origin, ["/slow"], proxyUrl);
      assert.equal(budget.ok, false);
      assert(budget.failures.some((v) => v.category === "performance" && v.score < 0.9));
    }
    return {
      clean: true,
      missingAlt: accessibility.violations.filter((v) => v.rule === "image-alt"),
      brokenLink: links.failures,
      externalNeverFetched: true,
      lighthouse: budget,
    };
  } finally {
    await close(proxy);
    await close(server);
    await close(forbidden);
  }
}
if (require.main === module)
  proof(process.argv.includes("--lighthouse"))
    .then((result) => console.log(JSON.stringify(result, null, 2)))
    .catch((error) => {
      console.error(error.message);
      process.exitCode = 1;
    });
module.exports = { proof };
