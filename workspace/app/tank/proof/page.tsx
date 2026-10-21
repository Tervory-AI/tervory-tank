import { goldIdentity } from "../../skala/gold/access";
import { notFound } from "next/navigation";
import { readProof } from "./server";
import { ProofView } from "./view";
import "./proof.css";

export const dynamic = "force-dynamic";
export const metadata = { title: "Tank proof · Tervory" };

export default async function ProofPage({ searchParams }: { searchParams: Promise<{ task?: string }> }) {
  const identity = await goldIdentity("platform");
  if (identity.role !== "founder") notFound();
  const { task } = await searchParams;
  try {
    return <ProofView data={await readProof(task)} task={task} />;
  } catch {
    return <section className="proof"><h1>Tank proof</h1><p role="alert">Proof evidence is unavailable. Try again when Tank is reachable.</p><a href="/tank">Back to Tank</a></section>;
  }
}
