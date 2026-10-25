import { baseBatches, baseRecords, listSkills } from "@/lib/tank";
import { loadContextReport, type ContextReport } from "./context-report";
import { activeTenant } from "@/lib/tenant";
import { buildModel, type BatchIn, type PageModel, type SkillIn } from "./model";

/**
 * Reads batch counts and approved skills from Tank.
 * Signed-out / no org → honest empty batches (not invented rows, not a load error).
 * Read only: nothing is queued, re-run or saved.
 */
export async function loadBase(): Promise<PageModel> {
  let batches: BatchIn[] | null = null;
  let skills: SkillIn[] | null = null;
  let contextTrial: ContextReport | null = null;
  const tenant = await activeTenant();
  if (!tenant) {
    batches = [];
  } else {
    try {
      batches = await baseBatches(tenant.tenantId);
      try {
        contextTrial = await loadContextReport(baseRecords);
      } catch {
        contextTrial = null;
      }
    } catch {
      batches = null;
    }
  }
  try {
    skills = await listSkills();
  } catch {
    skills = null;
  }
  return { ...buildModel({ batches, skills, now: new Date() }), contextTrial };
}
