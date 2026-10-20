import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { rejectUnlessFounder } from "@/app/review/access";
import { listSkills, type Skill } from "@/lib/tank";
import { activeTenant } from "@/lib/tenant";
import type { LibrarySkill } from "./library";
import { SkalaApp } from "./view";
import "./skala.css";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export const metadata: Metadata = { title: "Skala · Tervory" };

function asSkill(row: Skill): LibrarySkill {
  const state = typeof row.state === "string" ? row.state : "candidate";
  return {
    id: row.id,
    version: row.version,
    agent: row.agent,
    rung: Number(row.rung),
    task_type: row.task_type ?? null,
    description: row.description ?? "",
    state,
    last_eval_score: row.last_eval_score,
    last_eval_at: row.last_eval_at,
    present: row.present !== false,
  };
}

export default async function SkalaPage() {
  const denied = await rejectUnlessFounder();
  if (denied) notFound();

  let accountName: string | null = null;
  try {
    accountName = (await activeTenant())?.orgName ?? null;
  } catch {
    accountName = null;
  }

  let skills: LibrarySkill[] = [];
  let loadError: string | null = null;
  try {
    skills = (await listSkills()).map(asSkill);
  } catch {
    loadError = "The library could not be loaded. Reload the page.";
  }

  return <SkalaApp accountName={accountName} skills={skills} loadError={loadError} />;
}
