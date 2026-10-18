/** Moot Court is a training centre. Nothing here is a filed matter. */

export const MOOT_LABEL = "Moot Court";

export const MOOT_LEAD = "This is where Zenas trains.";

/** Students come later. This page has no sign-up. */
export const MOOT_LATER = "Law students will use it later, for free.";

export const MOOT_PARTS = [
  { id: "problem", title: "The problem", empty: "There is no training problem yet." },
  { id: "answer", title: "Zenas's answer", empty: "There is no answer yet." },
  { id: "correction", title: "The correction", empty: "There is no correction yet." },
] as const;

export type MootPartId = (typeof MOOT_PARTS)[number]["id"];

/** A stored round would be one civil problem, Zenas's answer, and the correction. */
export type TrainingRound = Record<MootPartId, string>;

/** No training problem is stored for this page yet. */
export function trainingRound(): TrainingRound | null {
  return null;
}
