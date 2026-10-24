/** Fixture match publish flags for MOOT-1a watch pages. No secrets. */

export type MatchRecord = {
  matchId: string;
  published: boolean;
  title: string;
  fairnessReading: string;
  judgmentOrder: string;
  reveal: string;
};

const FIXTURES: Record<string, MatchRecord> = {
  "fixture-unpublished": {
    matchId: "fixture-unpublished",
    published: false,
    title: "Fixture unpublished match",
    fairnessReading: "split",
    judgmentOrder: "appeal_dismissed",
    reveal: "Appeal dismissed.",
  },
  "fixture-published": {
    matchId: "fixture-published",
    published: true,
    title: "Fixture Landlord v Tenant (SCA) [TEST]",
    fairnessReading: "problem_may_be_lopsided",
    judgmentOrder: "appeal_dismissed",
    reveal: "Appeal dismissed. Notice was required before cancellation.",
  },
};

export function getMatch(matchId: string): MatchRecord | null {
  if (!/^[\w-]+$/.test(matchId)) return null;
  return FIXTURES[matchId] ?? null;
}
