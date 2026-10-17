import { auth } from "@clerk/nextjs/server";
import { headerLinks } from "../product-nav";
import { isListedFounder } from "../review/founder";
import { Lab } from "./lab";
import { catalogueCounts } from "./rig-server";

export const dynamic = "force-dynamic";

export default async function RigPage() {
  const { userId } = await auth();
  const founder = isListedFounder(userId, process.env.TERVORY_ADMIN_USER_IDS);
  const counts = catalogueCounts();
  return <Lab standardNav={headerLinks(founder)} products={counts.products} fits={counts.fits} live />;
}
