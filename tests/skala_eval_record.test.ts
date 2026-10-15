import assert from "node:assert/strict";
import { test } from "node:test";
import { caseRecord, splitPackages } from "../workspace/app/skala/record.ts";

test("a pass count alone is not a record", () => {
  const shown = caseRecord({
    total: 11,
    details: Array.from({ length: 11 }, (_, index) => ({
      case: index,
      name: `case ${index}`,
      passed: true,
      why: "ok",
    })),
  });
  assert.equal(shown.ok, false);
  if (!shown.ok) {
    assert.doesNotMatch(shown.message, /\d+\/\d+/);
    assert.doesNotMatch(shown.message, /\bpassed\b/i);
  }
});

test("every case keeps its goal and its result, including a pass", () => {
  const goal = { website: { value: "https://example.com", source: "input:verified", confidence: 85 } };
  const result = { website: { value: "https://example.com", source: "input:verified", confidence: 85 }, note: "from the run" };
  const missed = { website: { value: null, source: "none", confidence: 0 } };
  const shown = caseRecord({
    total: 2,
    details: [
      { case: 0, name: "verified hint", passed: true, why: "ok", goal, result },
      { case: 1, name: "nothing found", passed: false, why: "website: missing", goal: missed, result: missed },
    ],
  });
  assert.equal(shown.ok, true);
  if (!shown.ok) return;
  assert.equal(shown.cases.length, 2);
  assert.equal(shown.cases[0].name, "verified hint");
  assert.equal(shown.cases[0].passed, true);
  assert.equal(shown.cases[0].goal, JSON.stringify(goal));
  assert.equal(shown.cases[0].result, JSON.stringify(result));
  assert.equal(shown.cases[1].name, "nothing found");
  assert.equal(shown.cases[1].passed, false);
  assert.equal(shown.cases[1].goal, JSON.stringify(missed));
  assert.equal(shown.cases[1].result, JSON.stringify(missed));
});

test("the main list keeps the approved version and one newer unapproved version", () => {
  const rows = [
    { id: "base.find_site", version: "1.4.0", agent: "base", state: "retired" },
    { id: "base.find_site", version: "1.5.0", agent: "base", state: "retired" },
    { id: "base.find_site", version: "1.6.0", agent: "base", state: "approved" },
    { id: "base.find_site", version: "1.7.0", agent: "base", state: "staging" },
    { id: "base.find_site", version: "1.8.0", agent: "base", state: "candidate" },
  ];
  const { main, archive } = splitPackages(rows);
  assert.deepEqual(main.map((row) => row.version), ["1.6.0", "1.8.0"]);
  assert.deepEqual(archive.map((row) => row.version), ["1.4.0", "1.5.0", "1.7.0"]);
  assert.equal(rows.find((row) => row.version === "1.6.0")?.state, "approved");
});

test("with no newer version the approved one stays on the main list and older ones stay in the archive", () => {
  const rows = [
    { id: "base.find_site", version: "1.5.0", agent: "base", state: "retired" },
    { id: "base.find_site", version: "1.6.0", agent: "base", state: "approved" },
  ];
  const { main, archive } = splitPackages(rows);
  assert.deepEqual(main.map((row) => `${row.version} ${row.state}`), ["1.6.0 approved"]);
  assert.deepEqual(archive.map((row) => row.version), ["1.5.0"]);
});
