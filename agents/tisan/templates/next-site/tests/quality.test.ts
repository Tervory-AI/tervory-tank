import { createRequire } from "node:module";
import { expect, test } from "vitest";

const { lighthouseScores } = createRequire(import.meta.url)("../scripts/quality-check.cjs") as {
  lighthouseScores: (
    reports: object[],
    assertions: object,
  ) => {
    scores: { page: string; scores: Record<string, number> }[];
    failures: { page: string; category: string; score: number | null; threshold: number }[];
  };
};
const config = createRequire(import.meta.url)("../lighthouserc.cjs");
const report = (performance: number, accessibility = 1) => ({
  requestedUrl: "http://127.0.0.1:3000/test-page",
  categories: {
    performance: { score: performance },
    accessibility: { score: accessibility },
    "best-practices": { score: 1 },
    seo: { score: 1 },
  },
});

test("Lighthouse enforces the template's four founder-editable mobile budgets", () => {
  const assertions = config.ci.assert.assertions;
  expect(assertions["categories:accessibility"][1].minScore).toBe(0.95);
  expect(config.ci.collect.settings.formFactor).toBe("mobile");
  const result = lighthouseScores([report(0.89)], assertions);
  expect(result.failures).toContainEqual({
    page: "/test-page",
    category: "performance",
    score: 0.89,
    threshold: 0.9,
  });
  expect(lighthouseScores([report(1, 0.94)], assertions).failures[0].category).toBe(
    "accessibility",
  );
});

test("Lighthouse preserves all categories and uses its median run budget", () => {
  const result = lighthouseScores(
    [report(0.81), report(0.92), report(0.98)],
    config.ci.assert.assertions,
  );
  expect(result.failures).toEqual([]);
  expect(result.scores[0].scores).toEqual({
    performance: 0.92,
    accessibility: 1,
    "best-practices": 1,
    seo: 1,
  });
});

test("a missing Lighthouse score fails instead of disappearing", () => {
  const incomplete = { requestedUrl: "http://127.0.0.1:3000/test-page", categories: {} };
  const result = lighthouseScores([incomplete], config.ci.assert.assertions);
  expect(result.failures).toHaveLength(4);
  expect(result.failures.every((row) => row.score === null)).toBe(true);
});
