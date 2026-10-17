import { baseBatches, listSkills } from "@/lib/tank";
import { currentTenant } from "@/lib/tenant";
import { buildModel, type BatchIn, type PageModel, type SkillIn } from "./model";

/** Reads batch counts and approved skills from Tank. Read only: nothing is queued, re-run or saved. */
export async function loadBase(): Promise<PageModel> {
  let batches: BatchIn[] | null = null;
  let skills: SkillIn[] | null = null;
  try {
    const { tenantId } = await currentTenant();
    batches = await baseBatches(tenantId);
  } catch {
    batches = null;
  }
  try {
    skills = await listSkills();
  } catch {
    skills = null;
  }
  return buildModel({ batches, skills, now: new Date() });
}
