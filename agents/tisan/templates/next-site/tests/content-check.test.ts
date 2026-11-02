import { execFileSync, spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, expect, test } from "vitest";

import { checkContent, loadContent, validateSchema } from "../scripts/content-check.cjs";
import manifest from "../sections/manifest.json";
import fixture from "./fixtures/site.json";

const roots: string[] = [];
const fresh = () =>
  structuredClone(fixture) as {
    schema: string;
    nav: { label: string; href: string }[];
    ui: { menu_open: string; menu_close: string; skip_link: string };
    pages: {
      name: string;
      path: string;
      title: string;
      sections: { type: string; id: string; props: Record<string, unknown> }[];
    }[];
  };
function root() {
  const dir = mkdtempSync(join(tmpdir(), "tisan-content-"));
  roots.push(dir);
  return dir;
}
afterEach(() => roots.splice(0).forEach((dir) => rmSync(dir, { recursive: true, force: true })));

function save(dir: string, value: unknown) {
  mkdirSync(join(dir, "content"), { recursive: true });
  writeFileSync(join(dir, "content/site.json"), JSON.stringify(value));
}

test("the isolated fixture covers every manifest type, with optional slots omitted", () => {
  expect(checkContent(fixture)).toEqual([]);
  expect(fixture.pages[0].sections.map((section) => section.type).sort()).toEqual(
    Object.keys(manifest.sections).sort(),
  );
});

test("all missing text, image and alt slots are listed in one result", () => {
  const data = fresh();
  data.ui = {} as typeof data.ui;
  data.nav = [{}] as typeof data.nav;
  data.pages[0].title = " ";
  data.pages[0].sections = [
    { type: "image-text", id: "image", props: { side: "left" } },
    { type: "product-grid", id: "products", props: { items: [{ image: {} }, {}] } },
    { type: "gallery", id: "gallery", props: { images: [{ src: "", alt: " " }, {}] } },
  ];
  const errors = checkContent(data).join("\n");
  for (const path of [
    "site/ui/menu_open",
    "site/ui/menu_close",
    "site/ui/skip_link",
    "site/nav/0/label",
    "site/pages/0/title",
    "sections/0/props/heading",
    "sections/0/props/body",
    "sections/0/props/image/src",
    "sections/0/props/image/alt",
    "sections/1/props/items/0/name",
    "sections/1/props/items/0/image/src",
    "sections/1/props/items/0/image/alt",
    "sections/1/props/items/1/image/src",
    "sections/1/props/items/1/image/alt",
    "sections/2/props/images/0/src",
    "sections/2/props/images/0/alt",
    "sections/2/props/images/1/src",
    "sections/2/props/images/1/alt",
  ])
    expect(errors).toContain(path);
});

test.each(["unknown", "__proto__", "constructor", "header", "footer"])(
  "refuses unknown section %s",
  (type) => {
    const data = fresh();
    data.pages[0].sections[0].type = type;
    expect(checkContent(data).join("\n")).toContain("unknown section type");
  },
);

test("refuses bad types, enums, array bounds, string lengths, URLs and unknown props", () => {
  for (const props of [
    { heading: 1 },
    { heading: " " },
    { heading: "x".repeat(201) },
    { heading: "Test", extra: "value" },
    { heading: "Test", image: { src: "javascript:alert(1)", alt: "Test" } },
    { heading: "Test", cta: { href: "//outside.example", label: "Test" } },
  ]) {
    const data = fresh();
    data.pages[0].sections[0].props = props;
    expect(checkContent(data).length).toBeGreaterThan(0);
  }
  const data = fresh();
  data.pages[0].sections[3].props.side = "middle";
  data.pages[0].sections[4].props.items = [];
  data.nav = Array.from({ length: 9 }, () => ({ label: "Test", href: "/" }));
  const errors = checkContent(data).join("\n");
  expect(errors).toContain("invalid enum");
  expect(errors).toContain("too few items");
  expect(errors).toContain("too many items");
});

test("checks document shape, unique names/paths/ids and reserved routes", () => {
  for (const value of [
    null,
    [],
    1,
    {},
    { ...fresh(), schema: "other" },
    { ...fresh(), extra: true },
  ]) {
    expect(checkContent(value).length).toBeGreaterThan(0);
  }
  const data = fresh();
  data.pages.push(structuredClone(data.pages[0]));
  data.pages[0].sections.push(structuredClone(data.pages[0].sections[0]));
  expect(checkContent(data).filter((error) => error.includes("duplicate"))).toHaveLength(3);
  for (const path of ["/api/contact", "/_next/a", "/bad//path", "/../escape"]) {
    const invalid = fresh();
    invalid.pages[0].path = path;
    expect(checkContent(invalid).length).toBeGreaterThan(0);
  }
});

test("loadContent has no fixture fallback and refuses malformed or invalid content", () => {
  const dir = root();
  mkdirSync(join(dir, "tests/fixtures"), { recursive: true });
  cpSync("tests/fixtures/site.json", join(dir, "tests/fixtures/site.json"));
  expect(loadContent(dir)).toBeNull();
  save(dir, fresh());
  expect(loadContent(dir)).toEqual(fixture);
  save(dir, {});
  expect(() => loadContent(dir)).toThrow("site/schema");
  writeFileSync(join(dir, "content/site.json"), "{");
  expect(() => loadContent(dir)).toThrow();
});

test("CLI fails with all errors and succeeds for missing content", () => {
  const dir = root();
  const script = resolve("scripts/content-check.cjs");
  expect(execFileSync(process.execPath, [script], { cwd: dir, encoding: "utf8" })).toContain(
    "passed",
  );
  save(dir, {});
  const result = spawnSync(process.execPath, [script], { cwd: dir, encoding: "utf8" });
  expect(result.status).toBe(1);
  for (const slot of ["schema", "nav", "ui/menu_open", "ui/menu_close", "ui/skip_link", "pages"])
    expect(result.stderr).toContain(`site/${slot}`);
  const pkg = JSON.parse(readFileSync("package.json", "utf8"));
  expect(pkg.scripts.build).toBe("node scripts/content-check.cjs && next build");
});

test("unimplemented schema keywords fail closed", () => {
  const errors: string[] = [];
  validateSchema("Test", { type: "string", format: "email" }, "slot", errors);
  expect(errors).toEqual(["slot: unsupported schema keyword format"]);
});

test("invalid image objects still report missing source and alt text", () => {
  const data = fresh();
  data.pages[0].sections[3].props.image = null;
  const errors = checkContent(data).join("\n");
  expect(errors).toContain("sections/3/props/image/src");
  expect(errors).toContain("sections/3/props/image/alt");
});

test("empty page lists and existing contact/privacy content remain contract-valid", () => {
  const data = fresh();
  for (const path of ["/contact", "/privacy", "/Upper_Case/nested"]) {
    data.pages[0].path = path;
    expect(checkContent(data)).toEqual([]);
  }
  data.pages = [];
  expect(checkContent(data)).toEqual([]);
});
