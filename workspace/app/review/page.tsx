import { currentTenant } from "@/lib/tenant";
import { presentReview, type ReviewItem } from "@/app/api/zenas/rules";
import { homeRegion, zenas } from "@/app/api/zenas/tank";
import { requireReviewer } from "./access";
import { ReviewDesk } from "./desk";

export const dynamic = "force-dynamic";

export default async function ReviewPage() {
  const reviewer = await requireReviewer();
  let items: ReviewItem[] = [];
  let note = "";
  try {
    const { tenantId } = await currentTenant();
    const tags = reviewer.jurisdictions.join(",");
    const res = await zenas(
      `review?tenant_id=${tenantId}&home_region=${homeRegion()}&jurisdiction=${tags}`,
      { method: "GET" },
    );
    if (res.ok) items = presentReview(await res.json(), reviewer.jurisdictions);
    else if (res.status === 404) note = "The review queue is not on this server yet.";
    else note = "The review queue could not be loaded.";
  } catch {
    note = "The review queue could not be loaded.";
  }

  return (
    <>
      <picture>
        <source srcSet="/brand/tervory-logo-reversed.png" media="(prefers-color-scheme: dark)" />
        <img className="logo" src="/brand/tervory-logo-on-white.png" alt="Tervory" />
      </picture>
      <h1>Review</h1>
      <p className="lede">Read the draft beside its sources and the worked matters that were matched. Approve or reject it. Your name, admission number, and changes are recorded.</p>
      <ReviewDesk items={items} note={note} reviewer={`${reviewer.name} · ${reviewer.admissionNo}`} />
    </>
  );
}
