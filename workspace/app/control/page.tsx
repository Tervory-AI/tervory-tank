import { auth } from "@clerk/nextjs/server";
import { notFound } from "next/navigation";
import { isFounder } from "@/lib/admin";
import { readFounderDashboard, readPaidPause, readDashboardCandidates } from "@/lib/tank";
import { signupSource, payingSource } from "./sources";
import { readWorkers } from "./workers";
import { FounderDashboard } from "./view";
import "./dashboard.css";
export const dynamic = "force-dynamic";
export default async function ControlPage() {
  const { userId } = await auth();
  if (!userId || !isFounder(userId)) notFound();
  const results = await Promise.allSettled([readFounderDashboard(userId), signupSource(), payingSource(), readPaidPause(userId), readDashboardCandidates(userId), readWorkers(userId)]);
  const [data, signups, paying, pause, models, workers] = results;
  const labels = ["Work measurements unavailable.", "Clerk sign-ups unavailable.", "Stripe clients unavailable.", "Paid pause unavailable.", "Model comparisons unavailable.", "Workers status unavailable."];
  return <FounderDashboard view={{
    data: data.status === "fulfilled" ? data.value : null,
    signups: signups.status === "fulfilled" ? signups.value : null,
    paying: paying.status === "fulfilled" ? paying.value : null,
    paused: pause.status === "fulfilled" ? pause.value.paid_paused : null,
    refused: pause.status === "fulfilled" ? pause.value.refused ?? [] : [],
    models: models.status === "fulfilled" ? models.value : [],
    workers: workers.status === "fulfilled" ? workers.value : null,
    errors: results.flatMap((r,i) => r.status === "rejected" ? [labels[i]] : []),
  }} />;
}
