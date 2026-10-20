import { activeTenant } from "@/lib/tenant";
import { Lab } from "./lab";
import { catalogueCounts } from "./rig-server";
import { loadRigPlugins } from "./vault-server";

export const dynamic = "force-dynamic";

export default async function RigPage() {
  const counts = catalogueCounts();
  let accountName = "Your account";
  try {
    const tenant = await activeTenant();
    if (tenant?.orgName.trim()) accountName = tenant.orgName.trim();
  } catch {
    accountName = "Your account";
  }
  const plugins = await loadRigPlugins();
  return <Lab accountName={accountName} products={counts.products} fits={counts.fits} plugins={plugins} live />;
}
