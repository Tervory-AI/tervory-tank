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
// Illustrated prices and receipts match the founder-approved Figma prototype.
// They must never initiate a model, store action or payment.
if (existsSync("out/sign-up.html")) throw new Error("Public sign-up page is still exported");

const flat = home.replace(/\s+/g, " ");
const retired = ["one", "window"].join(" ");
if (flat.toLowerCase().includes(retired)) throw new Error("Homepage contains a retired phrase");

const required = [
  "Get early access", ">Join the list<", "Request early access",
  "Specialist AI that gets cheaper the more it works.",
  "Facts over hype. Work over fluff.",
  "What each product does", "Air-Gapped Cybersecurity",
  "Your shadow realm for digital threats.",
  "Attorney review is available as an option when you need it.",
  "Don’t Trust Marketing Claims. Read the Receipt.",
  "Stop Funding Silicon Valley’s Compute Waste.",
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
for (const id of ['id="engine"', 'id="squad"', 'id="receipt"', 'id="early"']) {
  if (!home.includes(id)) throw new Error(`Homepage is missing ${id}`);
}

// Every rendered static asset must be local, non-empty and included in export.
const sources = [...home.matchAll(/<img[^>]+src="([^"]+)"/g)].map(match => match[1]);
if (sources.length !== 22) throw new Error(`Expected 22 approved image slots; got ${sources.length}`);
for (const src of sources) {
  if (!src.startsWith("/home/")) throw new Error(`Unexpected image source ${src}`);
  for (const prefix of ["public", "out"]) {
    if (!existsSync(`${prefix}${src}`) || readFileSync(`${prefix}${src}`).length === 0) {
      throw new Error(`Empty or missing asset ${prefix}${src}`);
    }
  }
}
if (visible.includes("figma.com/api/mcp/asset")) throw new Error("Temporary Figma asset URL in page");
if ((visible.match(/class="squad-row"/g) || []).length !== 10) throw new Error("Expected ten squad products");

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
