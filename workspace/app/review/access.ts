import { auth, clerkClient } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";

export type Reviewer = {
  userId: string;
  name: string;
  admissionNo: string;
  jurisdictions: Array<"us" | "za">;
};

/** Clerk role `org:reviewer`, plus a jurisdiction tag and an admission number. */
export async function requireReviewer(): Promise<Reviewer> {
  const { userId, orgRole } = await auth();
  const role = (orgRole ?? "").replace(/^org:/, "");
  if (!userId || role !== "reviewer") notFound();
  const client = await clerkClient();
  const user = await client.users.getUser(userId);
  const meta = (user.publicMetadata ?? {}) as { jurisdiction?: unknown; admission_no?: unknown };
  const tag = typeof meta.jurisdiction === "string" ? meta.jurisdiction : "";
  const admissionNo = typeof meta.admission_no === "string" ? meta.admission_no.trim() : "";
  const jurisdictions: Array<"us" | "za"> = tag === "both" ? ["us", "za"] : tag === "us" || tag === "za" ? [tag] : [];
  if (!admissionNo || jurisdictions.length === 0) notFound();
  const name = [user.firstName, user.lastName].filter(Boolean).join(" ") || "Reviewer";
  return { userId, name, admissionNo, jurisdictions };
}
