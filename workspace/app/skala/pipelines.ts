/** One box per agent. The pipeline copies a library skill into that agent's own vault. */

export type AgentPipe = {
  squad: string;
  label: string;
  /** Official wordmark, used as-is on the navy band. */
  logo: string;
  vault?: string;
  /** This page does not copy into Tank. The pipeline is shown and the transfer waits. */
  holds: boolean;
};

export const AGENTS: AgentPipe[] = [
  { squad: "base", label: "Base", logo: "/brand/base-on-dark.png", vault: "base.vault", holds: false },
  { squad: "tiger", label: "Tiger", logo: "/brand/tiger-on-dark.png", vault: "tiger.vault", holds: false },
  { squad: "market_lab", label: "Market Lab", logo: "/brand/market-lab-on-dark.png", vault: "lab.vault", holds: false },
  { squad: "rig", label: "Rig", logo: "/brand/rig-on-dark.png", vault: "rig.vault", holds: false },
  { squad: "tisan", label: "Tisan", logo: "/brand/tisan-on-dark.png", vault: "tisan.vault", holds: false },
  { squad: "radix", label: "Radix", logo: "/brand/radix-on-dark.png", vault: "radix.vault", holds: false },
  { squad: "zenas", label: "Zenas", logo: "/brand/zenas-on-dark.png", vault: "zenas.vault", holds: false },
  { squad: "skala", label: "Skala", logo: "/brand/skala-on-dark.png", vault: "skala.vault", holds: false },
  { squad: "tank", label: "Tank", logo: "/brand/tank-on-dark.png", holds: true },
];

export const TRANSFER_WAITS = "This vault is off. The transfer waits.";
export const TANK_WAITS = "This pipeline waits.";

export type PipelineDestination = {
  squad: string;
  label: string;
  logo: string;
  enabled: boolean;
  waits: boolean;
};

function destination(agent: AgentPipe, enabled: boolean, waits: boolean): PipelineDestination {
  return { squad: agent.squad, label: agent.label, logo: agent.logo, enabled, waits };
}

export function waitingPipelines(): PipelineDestination[] {
  return AGENTS.map((agent) => destination(agent, false, true));
}
