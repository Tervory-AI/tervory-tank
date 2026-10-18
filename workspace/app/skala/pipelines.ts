/** One box per agent. The pipeline copies a library skill into that agent's own vault. */

export type AgentPipe = {
  squad: string;
  label: string;
  vault?: string;
  /** This page does not copy into Tank. The pipeline is shown and the transfer waits. */
  holds: boolean;
};

export const AGENTS: AgentPipe[] = [
  { squad: "base", label: "Base", vault: "base.vault", holds: false },
  { squad: "tiger", label: "Tiger", vault: "tiger.vault", holds: false },
  { squad: "market_lab", label: "Market Lab", vault: "lab.vault", holds: false },
  { squad: "rig", label: "Rig", vault: "rig.vault", holds: false },
  { squad: "tisan", label: "Tisan", vault: "tisan.vault", holds: false },
  { squad: "radix", label: "Radix", vault: "radix.vault", holds: false },
  { squad: "zenas", label: "Zenas", vault: "zenas.vault", holds: false },
  { squad: "skala", label: "Skala", vault: "skala.vault", holds: false },
  { squad: "tank", label: "Tank", holds: true },
];

export const TRANSFER_WAITS = "This vault is off. The transfer waits.";
export const TANK_WAITS = "This pipeline waits.";

export type PipelineDestination = {
  squad: string;
  label: string;
  enabled: boolean;
  waits: boolean;
};

export function waitingPipelines(): PipelineDestination[] {
  return AGENTS.map((agent) => ({
    squad: agent.squad,
    label: agent.label,
    enabled: false,
    waits: true,
  }));
}
