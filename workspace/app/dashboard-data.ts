import "server-only";

import { isFounder } from "@/lib/admin";
import { commandRequest, commandTools, readClientDashboard, readClientSavings, type CommandSquadGrant } from "@/lib/tank";
import type { Tenant } from "@/lib/tenant";
import type { Savings } from "./tank/proof/savings-types";

const team = [
  { agent: "base", name: "Base", description: "Business lists", href: "/base" },
  { agent: "tiger", name: "Tiger", description: "Prices", href: "/tiger" },
  { agent: "market_lab", name: "Market Lab", description: "Market research", href: "/market-lab" },
  { agent: "zenas", name: "Zenas", description: "Legal", href: "/zenas" },
] as const;

const statuses = { queued: "Queued", running: "In progress", done: "Ready", failed: "Failed" } as const;
const wholeNumber = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

async function grantedSquads(tenant: Tenant): Promise<Set<string>> {
  // Founders have every tool, irrespective of this tenant's actual grants.
  if (isFounder(tenant.userId)) {
    const grants: CommandSquadGrant[] = await (await commandRequest(tenant, "squads")).json();
    if (!Array.isArray(grants) || grants.some(row => !row || typeof row.agent !== "string" || typeof row.enabled !== "boolean")) {
      throw new Error("Dashboard squad data is unavailable.");
    }
    return new Set(grants.filter(row => row.enabled).map(row => row.agent));
  }
  // For clients, Tank derives this catalogue from tenant_squad on each request.
  return new Set((await commandTools(tenant)).map(tool => tool.split(".")[0]));
}

export async function loadDashboardData(tenant: Tenant) {
  const [dashboard, savings, grants] = await Promise.all([
    readClientDashboard(tenant.tenantId),
    readClientSavings<Savings>(tenant.tenantId, ""),
    grantedSquads(tenant),
  ]);
  // Missing sources must not become invented zeroes or approved empty states.
  if (!Number.isSafeInteger(dashboard.jobs_done) || dashboard.jobs_done < 0 || !Array.isArray(dashboard.recent)) {
    throw new Error("Dashboard job data is unavailable.");
  }
  const saved = savings?.month?.saved;
  if (typeof saved !== "string" || !/^-?\d+(?:\.\d+)?$/.test(saved) || !Number.isFinite(Number(saved)) || Math.abs(Number(saved)) > Number.MAX_SAFE_INTEGER) {
    throw new Error("Dashboard savings data is unavailable.");
  }
  const recent = dashboard.recent.slice(0, 4).map(job => {
    if (!job || typeof job.id !== "string" || !job.id || typeof job.title !== "string" || !job.title.trim() || !Object.hasOwn(statuses, job.status)) {
      throw new Error("Dashboard job data is unavailable.");
    }
    const status = job.status as keyof typeof statuses;
    return { id: job.id, title: job.title, status, label: statuses[status] };
  });
  return {
    jobsDone: wholeNumber.format(dashboard.jobs_done),
    saved: `$${wholeNumber.format(Number(saved))}`,
    recent,
    team: team.filter(member => grants.has(member.agent)),
  };
}
