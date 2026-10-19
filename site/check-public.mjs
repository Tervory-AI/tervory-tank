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

const flat = home.replace(/\s+/g, " ");
const retired = ["one", "window"].join(" ");
if (flat.toLowerCase().includes(retired)) throw new Error("Homepage contains a retired phrase");

const required = [
  "Get early access",
  ">Join the list<",
  "Tervory AI · In build",
  "Specialist AI for the work that runs a business.",
  "Tervory is a squad of specialist AI agents for data, pricing, markets, legal, security and the web.",
  "How it works",
  ">Ask.<",
  "Describe the job the way you would brief a colleague.",
  ">Routed.<",
  "Tank sends it to the specialist built for that job, on the best-value route that still gets it right.",
  ">Answered.<",
  "Every answer comes with its sources, the model that produced it, and the cost.",
  "It gets cheaper the more it works",
  "Most AI charges the same for the hundredth question as the first.",
  "The work stays right. The cost keeps falling.",
  "The squad",
  "Nine specialists. Each one built for a single job.",
  "Turns a raw list into verified businesses: websites, contacts and licences, each with a source.",
  "Watches prices and competitors, and tells you the moment a rival moves.",
  "Market research with every number sourced: demand, gaps, and shifts before they show.",
  "Finds the right product, and every part that fits it, in a retailer's own catalogue.",
  "Builds websites and apps from a short brief, tested before they go live.",
  "Finds what your systems and sites expose, before someone else does.",
  "Legal research and drafting for US and South African business law, reviewed by licensed lawyers.",
  "The skills library. Every skill is tested before a specialist may use it.",
  "The engine underneath. It routes every task to the best-value model and keeps the receipts.",
  "Measured, not promised",
  "Every skill passes a test set before it goes live.",
  "If we cannot measure it, we do not claim it.",
  "Be first in",
  "Leave your email and we will tell you when your seat is ready.",
  "Every answer shows its sources, the model that ran it, and what it cost.",
  "Tervory AI: specialist AI for the work that runs a business",
  "A squad of specialist AI agents for data, pricing, markets, legal, security and the web. Every answer shows its sources, the model that ran it, and what it cost.",
];
for (const line of required) {
  if (!flat.includes(line)) throw new Error(`Homepage is missing copy: ${line}`);
}
const retiredCopy = ["Email me when we release.", ">Send<", "Nothing is open yet."];
for (const line of retiredCopy) {
  if (flat.includes(line)) throw new Error(`Homepage still contains old copy: ${line}`);
}
if (!home.includes('action="/api/release-notice"')) {
  throw new Error("Release form does not post to the store");
}
if (home.includes('class="card"')) throw new Error("Products are still shown in cards");
for (const word of ["Brave", "Hawaii", "internal batch"]) {
  if (home.includes(word)) throw new Error(`Homepage contains ${word}`);
}
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
