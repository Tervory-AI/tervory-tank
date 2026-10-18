import { existsSync, readFileSync } from "node:fs";

const home = readFileSync("out/index.html", "utf8");
const robots = readFileSync("out/robots.txt", "utf8");
const sitemap = readFileSync("out/sitemap.xml", "utf8");

const banned = [
  "AmmoSync",
  "LOKD",
  "Custom Nation",
  "Shot Bonus",
  "TNGO",
  "case-study",
  "/internal",
  "app.tervory.com",
  "Sign in",
  "Sign up",
  "/sign-up",
  "Pricing",
  "has launched",
  "launch date",
];
for (const word of banned) {
  if (home.includes(word)) throw new Error(`Homepage contains ${word}`);
}
const visible = home.replace(/<script[\s\S]*?<\/script>/gi, "").replace(/<!--[\s\S]*?-->/g, "");
if (visible.includes("$")) throw new Error("Homepage contains a price");
if (existsSync("out/sign-up.html")) throw new Error("Public sign-up page is still exported");

if (!home.includes("Email me when we release.")) {
  throw new Error("Homepage is missing the release field");
}
if (!home.includes('action="/api/release-notice"')) {
  throw new Error("Release form does not post to the store");
}
if (!home.includes(">Send<")) throw new Error("Homepage is missing the send button");
if (!home.includes("Nothing is open yet.")) throw new Error("Homepage does not say the work is still closed");
for (const id of ['id="work"', 'id="products"']) {
  if (!home.includes(id)) throw new Error(`Homepage is missing ${id}`);
}

const marks = [
  "/brand/base-on-light.png",
  "/brand/tiger-on-light.png",
  "/brand/market-lab-on-light.png",
  "/brand/rig-on-light.png",
  "/brand/tisan-on-light.png",
  "/brand/radix-on-light.png",
  "/brand/zenas-on-light.png",
  "/brand/skala-on-light.png",
  "/brand/tank-on-light.png",
];
for (const mark of marks) {
  if (!home.includes(mark)) throw new Error(`Homepage is missing ${mark}`);
  if (!existsSync(`public${mark}`) && !existsSync(`out${mark}`)) {
    throw new Error(`Missing logo file ${mark}`);
  }
}

if (!robots.includes("Disallow: /internal/")) {
  throw new Error("robots.txt does not hide /internal/");
}
if (sitemap.includes("internal") || sitemap.includes("sign-up") || sitemap.includes("ammosync")) {
  throw new Error("Sitemap lists a page that is not the homepage");
}
if (!sitemap.includes("https://tervory.com/")) throw new Error("Sitemap is missing the homepage");

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
