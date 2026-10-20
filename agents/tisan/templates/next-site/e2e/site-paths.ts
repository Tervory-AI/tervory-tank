import { readFileSync } from "node:fs";
import { join } from "node:path";

export function sitePaths(): string[] {
  const text = readFileSync(join(process.cwd(), "lib", "site.ts"), "utf8");
  const hrefs = [...text.matchAll(/href:\s*"([^"]+)"/g)].map((match) => match[1]);
  if (hrefs.length === 0) {
    throw new Error("lib/site.ts has no pages");
  }
  return hrefs;
}
