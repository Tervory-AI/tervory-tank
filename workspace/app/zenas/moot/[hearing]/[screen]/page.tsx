import { currentTenant } from "@/lib/tenant";
import { notFound } from "next/navigation";
import { MootScreen } from "../../../moot-screen";
import "../../../zenas.css";
export default async function Page({ params }: { params: Promise<{hearing:string;screen:string}> }) {
  try { await currentTenant(); } catch { notFound(); }
  const {hearing,screen}=await params;
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(hearing)
      || !["bench","citations","feedback"].includes(screen))notFound();
  return <MootScreen id={hearing} kind={screen as "bench"|"citations"|"feedback"}/>;
}
