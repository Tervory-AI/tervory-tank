/** Evidence/export fields awaiting an approved Base page Figma frame. */
export const PAGE_FIELD_EXCLUSIONS: readonly string[] = [
  "phone_e164",
  "phone_valid",
  "phone_line_type",
  "email_syntax_ok",
  "email_disposable",
];

export function pageFieldEntries<T>(fields: Record<string, T>): [string, T][] {
  return Object.entries(fields).filter(([name]) => !PAGE_FIELD_EXCLUSIONS.includes(name));
}
