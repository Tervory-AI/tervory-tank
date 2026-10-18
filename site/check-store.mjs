import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { storeAddress } from "./release-store.mjs";

const dir = mkdtempSync(join(tmpdir(), "tervory-release-"));
const file = join(dir, "signups.jsonl");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const saved = await storeAddress(file, "  ada@example.com  ");
assert(saved.stored === true && saved.status === 200, "a valid address was not stored");
const first = readFileSync(file, "utf8");
assert(first.includes('"email":"ada@example.com"'), "the file does not contain the address");

const again = await storeAddress(file, "ada@example.com");
assert(again.stored === true, "an address already on file was reported as dropped");

const bad = await storeAddress(file, "not-an-email");
assert(bad.stored === false && bad.status === 400, "an invalid address was accepted");
assert(!readFileSync(file, "utf8").includes("not-an-email"), "an invalid address was written");

const blocked = join(dir, "not-a-directory");
writeFileSync(blocked, "x");
const dropped = await storeAddress(join(blocked, "signups.jsonl"), "dropped@example.com");
assert(dropped.stored === false && dropped.status === 500, "an unwritable path reported success");
assert(!readFileSync(file, "utf8").includes("dropped@example.com"), "a dropped address was written elsewhere");

const port = 3099;
let logs = "";
const child = spawn(
  process.execPath,
  ["server.mjs", "--port", String(port), "--file", file, "--root", "out"],
  { stdio: ["ignore", "pipe", "pipe"] },
);
child.stdout.on("data", (chunk) => {
  logs += chunk.toString();
});
child.stderr.on("data", (chunk) => {
  logs += chunk.toString();
});

async function waitForServer() {
  const started = Date.now();
  while (Date.now() - started < 5000) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      if (response.status === 200 || response.status === 404) return;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }
  throw new Error(`server did not start\n${logs}`);
}

try {
  await waitForServer();
  const json = await fetch(`http://127.0.0.1:${port}/api/release-notice`, {
    method: "POST",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify({ email: "grace@example.com" }),
  });
  const body = await json.json();
  assert(json.status === 200 && body.stored === true, "JSON submit did not confirm the write");
  assert(readFileSync(file, "utf8").includes('"email":"grace@example.com"'), "JSON submit did not write the address");

  const html = await fetch(`http://127.0.0.1:${port}/api/release-notice`, {
    method: "POST",
    headers: { accept: "text/html", "content-type": "application/x-www-form-urlencoded" },
    body: "email=nope",
  });
  const htmlText = await html.text();
  assert(html.status === 400, "an invalid form post was not rejected");
  assert(htmlText.includes("That address was not saved."), "a dropped form post hid the failure");
  assert(!htmlText.includes("We'll email this address when we release."), "a dropped form post showed success");

  const page = await fetch(`http://127.0.0.1:${port}/api/release-notice`, {
    method: "POST",
    headers: { accept: "text/html", "content-type": "application/x-www-form-urlencoded" },
    body: "email=june@example.com",
  });
  const pageText = await page.text();
  assert(page.status === 200 && pageText.includes("We'll email this address when we release."), "a stored form post did not confirm");
  assert(readFileSync(file, "utf8").includes('"email":"june@example.com"'), "an HTML form post did not write the address");

  const get = await fetch(`http://127.0.0.1:${port}/api/release-notice`, {
    headers: { accept: "text/html" },
  });
  const getText = await get.text();
  assert(get.status === 405, "GET was treated as a submit");
  assert(!getText.includes("We'll email this address when we release."), "GET showed success");

  const home = await fetch(`http://127.0.0.1:${port}/`);
  const homeText = await home.text();
  assert(home.status === 200, "homepage was not served");
  assert(homeText.includes("Email me when we release."), "served homepage is missing the field");

  const hidden = await fetch(`http://127.0.0.1:${port}/internal/ammosync.html`);
  assert(hidden.headers.get("x-robots-tag") === "noindex, nofollow", "/internal is missing noindex");
} finally {
  child.kill();
}

assert(!logs.includes("ada@example.com"), "the server log contains an address");
assert(!logs.includes("grace@example.com"), "the server log contains an address");
assert(!logs.includes("june@example.com"), "the server log contains an address");

const badPort = 3100;
const badChild = spawn(
  process.execPath,
  ["server.mjs", "--port", String(badPort), "--file", join(blocked, "signups.jsonl"), "--root", "out"],
  { stdio: "ignore" },
);
let failedWriteChecked = false;
try {
  const started = Date.now();
  while (Date.now() - started < 5000) {
    try {
      const response = await fetch(`http://127.0.0.1:${badPort}/api/release-notice`, {
        method: "POST",
        headers: { accept: "application/json", "content-type": "application/json" },
        body: JSON.stringify({ email: "lost@example.com" }),
      });
      const body = await response.json();
      assert(response.status === 500 && body.stored === false, "a failed write returned success");
      failedWriteChecked = true;
      break;
    } catch (error) {
      if (Date.now() - started >= 4900) throw error;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  }
} finally {
  badChild.kill();
}
assert(failedWriteChecked, "a failed write was not checked");

rmSync(dir, { recursive: true, force: true });
console.log("Release store check passed.");
