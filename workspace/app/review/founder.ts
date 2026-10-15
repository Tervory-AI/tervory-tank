// Same allow-list as isFounder in workspace/lib/admin.ts.
// TERVORY_ADMIN_USER_IDS is a comma-separated list of Clerk user ids.

export type FounderDenial = { error: "Not found"; status: 404 };

export function isListedFounder(userId: string | null | undefined, raw: string | null | undefined): boolean {
  if (!userId) return false;
  const allowed = (raw ?? "").split(",").map((part) => part.trim()).filter((part) => part.length > 0);
  return allowed.includes(userId);
}

/** A signed-in customer is rejected. The list is the same one the admin page uses. */
export function founderDenial(userId: string | null | undefined, raw: string | null | undefined): FounderDenial | null {
  if (isListedFounder(userId, raw)) return null;
  return { error: "Not found", status: 404 as const };
}
