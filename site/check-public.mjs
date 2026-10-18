import { existsSync, readFileSync } from "node:fs";

const home = readFileSync("out/index.html", "utf8");
const signup = readFileSync("out/sign-up.html", "utf8");
const robots = readFileSync("out/robots.txt", "utf8");
const sitemap = readFileSync("out/sitemap.xml", "utf8");

const banned = ["AmmoSync", "LOKD", "Custom Nation", "Shot Bonus", "TNGO", "case-study", "/internal"];
for (const word of banned) {
  if (home.includes(word) || signup.includes(word)) {
    throw new Error(`Public page contains ${word}`);
  }
}

for (const id of ['id="how"', 'id="tank"', 'id="squad"', 'id="ledger"', 'id="pricing"']) {
  if (!home.includes(id)) throw new Error(`Homepage is missing ${id}`);
}

const marks = [
  "/brand/base-on-light.png",
  "/brand/tiger-on-light.png",
  "/brand/market-lab-on-light.png",
  "/brand/radix-on-light.png",
  "/brand/tisan-on-light.png",
  "/brand/zenas-on-light.png",
];
for (const mark of marks) {
  if (!home.includes(mark)) throw new Error(`Homepage is missing ${mark}`);
}
if (home.includes('class="glyph"')) throw new Error("Homepage still has letter tiles");

if (!home.includes("https://app.tervory.com/sign-up")) {
  throw new Error("Homepage Start button does not open the app");
}
if (!home.includes('href="/sign-up"')) {
  throw new Error("Homepage does not link to the public sign-up page");
}
if (!signup.includes("https://app.tervory.com/sign-up")) {
  throw new Error("Sign-up page does not continue to the app");
}
if (!signup.includes("https://app.tervory.com/sign-in")) {
  throw new Error("Sign-up page does not link to sign in");
}

if (!robots.includes("Disallow: /internal/")) {
  throw new Error("robots.txt does not hide /internal/");
}
if (sitemap.includes("internal") || sitemap.includes("ammosync")) {
  throw new Error("Sitemap lists a hidden page");
}
if (!sitemap.includes("https://tervory.com/sign-up")) {
  throw new Error("Sitemap is missing the sign-up page");
}

const hidden = [
  "out/internal/ammosync.html",
  "out/internal/lokd-security.html",
  "out/internal/custom-nation.html",
  "out/internal/shot-bonus.html",
  "out/internal/tngo.html",
];
for (const path of hidden) {
  if (!existsSync(path)) throw new Error(`Missing hidden page ${path}`);
  const html = readFileSync(path, "utf8");
  if (!html.includes("noindex")) throw new Error(`${path} is missing noindex`);
}

console.log("Public pages check passed.");
