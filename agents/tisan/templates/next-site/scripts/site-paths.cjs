const { existsSync } = require("node:fs");
const { join } = require("node:path");
const { loadContent } = require("./content-check.cjs");

function sitePaths() {
  const root = join(__dirname, "..");
  const paths = (loadContent(root)?.pages || []).map((page) => page.path);
  for (const name of ["contact", "privacy"]) {
    if (existsSync(join(root, "app", name, "page.tsx"))) paths.push(`/${name}`);
  }
  return [...new Set(paths)];
}
module.exports = { sitePaths };
