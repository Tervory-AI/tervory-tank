import { auth, clerkClient } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { founderDenial, isListedFounder, reviewGate, type FounderDenial } from "./founder";

export type Reviewer = {
  userId: string;
  name: string;
  admissionNo: string;
  jurisdictions: Array<"us" | "za">;
  founder: boolean;
  role: string;
};

/** Clerk role `org:reviewer`, plus a jurisdiction tag and an admission number. Founders open the same page. */
export async function requireReviewer(): Promise<Reviewer> {
  const { userId, orgRole } = await auth();
  const role = (orgRole ?? "").replace(/^org:/, "");
  const founder = isListedFounder(userId, process.env["TERVORY_ADMIN_USER_IDS"]);
  if (!userId || (!founder && role !== "reviewer")) notFound();
  const client = await clerkClient();
  const user = await client.users.getUser(userId);
  const meta = (user.publicMetadata ?? {}) as { jurisdiction?: unknown; admission_no?: unknown };
  const gate = reviewGate({
    userId,
    orgRole,
    adminIds: process.env["TERVORY_ADMIN_USER_IDS"],
    jurisdiction: meta.jurisdiction,
    admissionNo: meta.admission_no,
  });
  if (!gate) notFound();
  const name = [user.firstName, user.lastName].filter(Boolean).join(" ") || (gate.founder ? "Founder" : "Reviewer");
  return { userId, name, admissionNo: gate.admissionNo, jurisdictions: gate.jurisdictions, founder: gate.founder, role };
}

/** Skala and Tank. Same Clerk user list as the admin page (`TERVORY_ADMIN_USER_IDS`). */
export async function rejectUnlessFounder(): Promise<FounderDenial | null> {
  const { userId } = await auth();
  return founderDenial(userId, process.env["TERVORY_ADMIN_USER_IDS"]);
}
