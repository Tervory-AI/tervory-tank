import { loadContent } from "../scripts/content-check.cjs";
import type manifest from "../sections/manifest.json";

export type SectionType = keyof typeof manifest.sections;
export type ContentSection = {
  type: SectionType;
  id: string;
  props: Record<string, unknown>;
};
export type ContentPage = {
  name: string;
  path: string;
  title: string;
  sections: ContentSection[];
};
export type SiteContent = {
  schema: "tisan.content/1";
  logo?: { src: string; alt: string };
  nav: { label: string; href: string }[];
  footer?: { text?: string; links?: { label: string; href: string }[] };
  ui: { menu_open: string; menu_close: string; skip_link: string };
  pages: ContentPage[];
};

// The same validation runs before build and before any content is rendered.
// No test-content fallback is allowed here.
export function readContent(): SiteContent | null {
  return loadContent();
}
