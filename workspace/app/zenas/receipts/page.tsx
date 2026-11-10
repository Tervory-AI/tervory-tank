import {currentTenant} from "@/lib/tenant";
import {zenas} from "@/app/api/zenas/tank";
import {Receipts} from "./view";
import "../zenas.css";

export const dynamic="force-dynamic";
export default async function ReceiptPage(){
  const {tenantId}=await currentTenant();
  try {
    const response=await zenas(`receipts?tenant_id=${encodeURIComponent(tenantId)}`,{method:"GET"});
    if(!response.ok)throw new Error('unavailable');
    const data=await response.json();
    return <main className="zn"><h1>Zenas</h1><Receipts receipts={data.receipts}/></main>;
  } catch {
    return <main className="zn"><h1>Zenas</h1><p role="alert">Room unavailable</p></main>;
  }
}
