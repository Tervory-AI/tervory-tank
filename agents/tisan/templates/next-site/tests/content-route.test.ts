import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, expect, test, vi } from "vitest";

import ContentRoute, { generateMetadata } from "../app/[[...path]]/page";
import { readContent, type SiteContent } from "../lib/content";
import manifest from "../sections/manifest.json";
import { sectionRegistry } from "../sections/registry";
import fixture from "./fixtures/site.json";

vi.mock("../lib/content", () => ({ readContent: vi.fn() }));
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("not-found");
  },
}));
const content = () => structuredClone(fixture) as SiteContent;
const props = (path?: string[]) => ({ params: Promise.resolve({ path }) });
beforeEach(() => vi.mocked(readContent).mockReturnValue(null));

test("missing content renders no home words and unknown paths are not found", async () => {
  expect(await ContentRoute(props())).toBeNull();
  await expect(ContentRoute(props(["about"]))).rejects.toThrow("not-found");
  expect(await generateMetadata(props())).toEqual({});
});

test("every manifest type has an empty renderer pending its Figma frame", async () => {
  expect(Object.keys(sectionRegistry).sort()).toEqual(Object.keys(manifest.sections).sort());
  for (const renderer of Object.values(sectionRegistry)) expect(renderer({})).toBeNull();
  vi.mocked(readContent).mockReturnValue(content());
  expect(renderToStaticMarkup(await ContentRoute(props()))).toBe("");
  expect(await generateMetadata(props())).toEqual({ title: fixture.pages[0].title });
});

test("the same route resolves nested content paths without creating a default home", async () => {
  const data = content();
  data.pages[0].path = "/one/two";
  vi.mocked(readContent).mockReturnValue(data);
  expect(renderToStaticMarkup(await ContentRoute(props(["one", "two"])))).toBe("");
  expect(await generateMetadata(props(["one", "two"]))).toEqual({ title: data.pages[0].title });
  expect(await ContentRoute(props())).toBeNull();
  await expect(ContentRoute(props(["missing"]))).rejects.toThrow("not-found");
});
