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

export type ReviewGateInput = {
  userId: string | null | undefined;
  orgRole: string | null | undefined;
  adminIds: string | null | undefined;
  jurisdiction: unknown;
  admissionNo: unknown;
};

export type ReviewGateResult = {
  founder: boolean;
  admissionNo: string;
  jurisdictions: Array<"us" | "za">;
};

/** Founders and complete reviewers may open /review. Anyone else is refused. */
export function reviewGate(input: ReviewGateInput): ReviewGateResult | null {
  if (!input.userId) return null;
  const founder = isListedFounder(input.userId, input.adminIds);
  const role = (input.orgRole ?? "").replace(/^org:/, "");
  if (!founder && role !== "reviewer") return null;
  const tag = typeof input.jurisdiction === "string" ? input.jurisdiction : "";
  const admissionNo = typeof input.admissionNo === "string" ? input.admissionNo.trim() : "";
  const tagged: Array<"us" | "za"> = tag === "both" ? ["us", "za"] : tag === "us" || tag === "za" ? [tag] : [];
  if (!founder && (!admissionNo || tagged.length === 0)) return null;
  return {
    founder,
    admissionNo,
    jurisdictions: tagged.length > 0 ? tagged : ["us", "za"],
  };
}
