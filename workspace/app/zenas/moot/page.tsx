import { currentTenant } from "@/lib/tenant";
import { notFound } from "next/navigation";
import { MootCourt } from "../moot-court";
import "../zenas.css";
export default async function Page() {
  try { await currentTenant(); } catch { notFound(); }
  return <main className="zn"><MootCourt/></main>;
}
