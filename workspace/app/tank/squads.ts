// One box and one pipeline for each agent. No vault contents.

export const SQUADS = [
  { id: "base", name: "Base", logo: "/brand/base-on-dark.png" },
  { id: "tiger", name: "Tiger", logo: "/brand/tiger-on-dark.png" },
  { id: "market-lab", name: "Market Lab", logo: "/brand/market-lab-on-dark.png" },
  { id: "rig", name: "Rig", logo: "/brand/rig-on-dark.png" },
  { id: "tisan", name: "Tisan", logo: "/brand/tisan-on-dark.png" },
  { id: "radix", name: "Radix", logo: "/brand/radix-on-dark.png" },
  { id: "zenas", name: "Zenas", logo: "/brand/zenas-on-dark.png" },
  { id: "skala", name: "Skala", logo: "/brand/skala-on-dark.png" },
  { id: "tank", name: "Tank", logo: "/brand/tank-on-dark.png" },
] as const;

export type Squad = (typeof SQUADS)[number];

export const SQUAD_LINE =
  "A squad cannot read another squad's vault, and cannot read the platform keys.";

export function pipelineTo(name: string): string {
  return `Pipeline to ${name}`;
}

export type ModelRow = { name: string };

export const MODEL_KEY_LINE = "The key is held by LiteLLM.";

export function modelsMatching(query: string, rows: readonly ModelRow[]): ModelRow[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...rows];
  return rows.filter((row) => row.name.toLowerCase().includes(needle));
}

export function squadsMatching(query: string, squads: readonly Squad[] = SQUADS): Squad[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...squads];
  return squads.filter((squad) => {
    const blob = `${squad.name} box ${pipelineTo(squad.name)}`.toLowerCase();
    return blob.includes(needle);
  });
}
