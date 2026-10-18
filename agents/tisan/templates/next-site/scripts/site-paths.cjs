const { readFileSync } = require("node:fs");
const { join } = require("node:path");

function sitePaths() {
  const text = readFileSync(join(__dirname, "..", "lib", "site.ts"), "utf8");
  const hrefs = [...text.matchAll(/href:\s*"([^"]+)"/g)].map((match) => match[1]);
  if (hrefs.length === 0) {
    throw new Error("lib/site.ts has no pages");
  }
  return hrefs;
}

module.exports = { sitePaths };
