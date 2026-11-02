export function loadContent(root?: string): import("../lib/content").SiteContent | null;
export function checkContent(content: unknown): string[];
export function validateSchema(
  value: unknown,
  schema: object,
  path: string,
  errors: string[],
): void;
