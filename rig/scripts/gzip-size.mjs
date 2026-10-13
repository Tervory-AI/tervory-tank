import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

const limit = 150 * 1024;
let failed = false;

for (const name of readdirSync("dist")) {
  if (!/\.(js|cjs|mjs)$/.test(name)) continue;
  const raw = readFileSync(new URL(`../dist/${name}`, import.meta.url));
  const gzip = gzipSync(raw).length;
  console.log(`${name}: ${raw.length} bytes, gzip ${gzip}`);
  if (gzip > limit) {
    console.error(`${name} is over 150 KB gzipped`);
    failed = true;
  }
}

if (failed) process.exit(1);
