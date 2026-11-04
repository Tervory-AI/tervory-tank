import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const site = fileURLToPath(new URL("../site/", import.meta.url));
const dir = mkdtempSync(join(tmpdir(), "tervory-canonical-"));
const store = join(dir, "signups.jsonl");
writeFileSync(join(dir, "index.html"), "<p>isolated canonical fixture</p>");
const child = spawn(process.execPath, ["server.mjs", "--root", dir, "--file", store, "--port", "0"], {
  cwd: site, stdio: ["ignore", "pipe", "pipe"],
});
let logs = "";
child.stderr.on("data", (chunk) => { logs += chunk; });
const portReady = new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error(`server startup timeout: ${logs}`)), 5000);
  child.once("error", (error) => { clearTimeout(timer); reject(error); });
  child.once("exit", (code) => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${logs}`)); });
  child.stdout.on("data", (chunk) => {
    logs += chunk;
    const match = logs.match(/site listening on (\d+)/);
    if (match) { clearTimeout(timer); resolve(Number(match[1])); }
  });
});

function call(port, host, path = "/", method = "GET", extra = {}, body) {
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port, path, method, headers: { host, ...extra } }, (res) => {
      let data = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
    });
    req.on("error", reject);
    req.end(body);
  });
}

try {
  const port = await portReady;
  for (const method of ["GET", "HEAD"]) {
    for (const path of ["/", "/internal/example?ref=one&ref=two", "/a%2Fb/%E2%9C%93?next=https%3A%2F%2Fother.example%2F&x=%2B", "//other.example/path?q=1"]) {
      const result = await call(port, "www.tervory.com", path, method);
      assert.equal(result.status, 308, `${method} ${path}`);
      assert.equal(result.headers.location, "https://tervory.com" + path);
      assert.equal(result.body, "");
    }
  }
  for (const host of ["WWW.TERVORY.COM", "www.tervory.com:443", "www.tervory.com."]) {
    assert.equal((await call(port, host)).headers.location, "https://tervory.com/");
  }
  for (const host of ["tervory.com", "127.0.0.1", "localhost:3000", "www.tervory.com.other.example"]) {
    const result = await call(port, host, "/", "GET", { "x-forwarded-host": "www.tervory.com" });
    assert.equal(result.status, 200, host);
    assert.equal(result.headers.location, undefined);
    assert.match(result.body, /isolated canonical fixture/);
  }
  assert.equal((await call(port, "tervory.com", "/", "HEAD")).body, "");
  assert.equal((await call(port, "tervory.com", "/missing")).status, 404);
  const initial = await call(port, "www.tervory.com", "/?release=1");
  const target = new URL(initial.headers.location);
  const final = await call(port, target.host, target.pathname + target.search);
  assert.equal(final.status, 200); // one canonical hop; no loop on apex
  assert.equal(final.headers.location, undefined);
  const body = JSON.stringify({ email: "canonical-fixture@example.com" });
  const headers = { "content-type": "application/json", accept: "application/json" };
  const redirect = await call(port, "www.tervory.com", "/api/release-notice?ref=www", "POST", headers, body);
  assert.equal(redirect.status, 308); // preserves POST for a client following the redirect
  assert.equal(redirect.headers.location, "https://tervory.com/api/release-notice?ref=www");
  assert.equal(existsSync(store), false); // alias has not written a duplicate signup
  const saved = await call(port, "tervory.com", "/api/release-notice?ref=www", "POST", headers, body);
  assert.equal(saved.status, 200);
  assert.equal(JSON.parse(saved.body).stored, true);
  assert.match(readFileSync(store, "utf8"), /canonical-fixture@example.com/);
  assert.equal((await call(port, "tervory.com", "/api/release-notice")).status, 405);
  console.log("Canonical redirect, escaped paths/queries, exact host, apex health and signup checks passed.");
} finally {
  if (child.exitCode == null) {
    const exited = once(child, "exit");
    child.kill("SIGTERM");
    await exited;
  }
  rmSync(dir, { recursive: true, force: true });
}
