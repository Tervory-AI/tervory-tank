// One box and one pipeline for each agent. No vault contents.

export const SQUADS = [
  { id: "base", name: "Base" },
  { id: "tiger", name: "Tiger" },
  { id: "market-lab", name: "Market Lab" },
  { id: "rig", name: "Rig" },
  { id: "tisan", name: "Tisan" },
  { id: "radix", name: "Radix" },
  { id: "zenas", name: "Zenas" },
  { id: "skala", name: "Skala" },
  { id: "tank", name: "Tank" },
] as const;

export type Squad = (typeof SQUADS)[number];

export const SQUAD_LINE =
  "A squad cannot read another squad's vault, and cannot read the platform keys.";

export function pipelineTo(name: string): string {
  return `Pipeline to ${name}`;
}

export type ModelRow = { name: string; keyMissing: boolean };

export function modelsMatching(query: string, rows: readonly ModelRow[]): ModelRow[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...rows];
  return rows.filter((row) => {
    const blob = `${row.name}${row.keyMissing ? " key is missing" : ""}`.toLowerCase();
    return blob.includes(needle);
  });
}

export function squadsMatching(query: string, squads: readonly Squad[] = SQUADS): Squad[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return [...squads];
  return squads.filter((squad) => {
    const blob = `${squad.name} box ${pipelineTo(squad.name)}`.toLowerCase();
    return blob.includes(needle);
  });
}
