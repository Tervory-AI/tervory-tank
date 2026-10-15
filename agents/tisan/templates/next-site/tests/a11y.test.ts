import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "vitest";

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "playwright-report") {
      continue;
    }
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      walk(path, out);
    } else {
      out.push(path);
    }
  }
  return out;
}

test("layout has landmarks and the document language", () => {
  const layout = readFileSync("app/layout.tsx", "utf8");
  expect(layout).toContain("<html");
  expect(layout).toContain("lang={site.locale}");
  expect(layout).toContain("<header");
  expect(layout).toContain("<nav");
  expect(layout).toContain('aria-label="Primary"');
  expect(layout).toContain("<main");
  expect(layout).toContain("<footer");
});

test("focus is visible", () => {
  const css = readFileSync("app/globals.css", "utf8");
  expect(css).toContain(":focus-visible");
});

test("brand colours live in tokens", () => {
  const css = readFileSync("app/tokens.css", "utf8");
  for (const name of ["ink", "paper", "accent", "line"]) {
    expect(css).toContain(`--colour-${name}:`);
  }
  expect(css).toContain("--font-heading:");
  expect(css).toContain("--font-body:");
});

test("components do not hard-code colours", () => {
  const files = walk(".").filter(
    (path) => (path.endsWith(".tsx") || path.endsWith(".css")) && !path.endsWith("app/tokens.css"),
  );
  for (const path of files) {
    expect(readFileSync(path, "utf8"), path).not.toMatch(/#[0-9A-Fa-f]{3,8}\b/);
  }
});

test("the logo has alternative text when a logo is set", () => {
  const layout = readFileSync("app/layout.tsx", "utf8");
  expect(layout).toContain("alt={`${site.name} logo`}");
});

test("contact form posts to the placeholder and has labels", () => {
  if (!existsSync("app/contact/page.tsx")) {
    return;
  }
  const page = readFileSync("app/contact/page.tsx", "utf8");
  expect(page).toContain('action="/api/contact"');
  expect(page).toContain('method="post"');
  expect(page).toContain("<label");
  expect(page).toContain('htmlFor="contact-name"');
  expect(page).toContain('htmlFor="contact-email"');
  expect(page).toContain('htmlFor="contact-message"');
  const route = readFileSync("app/api/contact/route.ts", "utf8");
  expect(route).toContain("status: 202");
});
