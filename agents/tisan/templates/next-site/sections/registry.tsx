import type { ContentSection, SectionType } from "../lib/content";

type SectionComponent = (props: Record<string, unknown>) => null;
const pendingDesign: SectionComponent = () => null;

// Each visual remains empty until its approved Figma frame is available.
export const sectionRegistry: Record<SectionType, SectionComponent> = {
  hero: pendingDesign,
  "feature-grid": pendingDesign,
  "product-grid": pendingDesign,
  "image-text": pendingDesign,
  steps: pendingDesign,
  faq: pendingDesign,
  "cta-band": pendingDesign,
  contact: pendingDesign,
  gallery: pendingDesign,
};

export function RenderSections({ sections }: { sections: ContentSection[] }) {
  return sections.map((section) => {
    const Component = sectionRegistry[section.type];
    return <Component key={section.id} {...section.props} />;
  });
}
