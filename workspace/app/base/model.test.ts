import assert from "node:assert/strict";
import test from "node:test";
import { contextReport, loadContextReport, PLATFORM_TENANT } from "./context-report";
import type { BaseRecord } from "@/lib/tank";
import { approvedSkills, batchStatus, buildModel, refreshedLabel, shortDate, type BatchIn, type SkillIn } from "./model";

test("trial report reads only platform records", async () => {
  const calls: string[] = [];
  await loadContextReport(async (tenantId, options) => {
    calls.push(tenantId);
    assert.equal(options.limit, 200);
    assert.notEqual(tenantId, "client-tenant");
    return [];
  });
  assert.deepEqual(calls, [PLATFORM_TENANT]);
});

test("credit cap reached is shown without counting an uncalled record as a charge", () => {
  const row = { passes: { context_dev: { status: "credit_limit", message: "credit cap reached" } } } as unknown as BaseRecord;
  const report = contextReport([row]);
  assert.equal(report.creditCapReached, true);
  assert.equal(report.records, 0);
  assert.equal(report.unknownCharges, 0);
});

test("trial accuracy uses checked answers, includes missing answers and unknown charges", () => {
  const record = {
    profile: { website: { value: "https://example.com" } },
    passes: {
      context_dev: { status: "candidate", fields: { website: "https://wrong.example" }, credits: 10 },
      context_dev_checked: { checked: true, expected: { website: "https://example.com", name: "Example" } },
    },
  } as unknown as BaseRecord;
  const unchecked = { ...record, passes: { context_dev: { status: "failed", credits: null } } } as unknown as BaseRecord;
  const report = contextReport([record, unchecked]);
  assert.equal(report.records, 2);
  assert.equal(report.creditsPerRecord, null);
  assert.equal(report.unknownCharges, 1);
  assert.deepEqual(report.fields[0], { field: "website", checked: 1, baseCorrect: 1, contextCorrect: 0 });
  assert.equal(report.fields[1].contextCorrect, 0);
  assert.equal(contextReport([record]).creditsPerRecord, 10);
});

test("social comparison accepts source formats with the same checked links", () => {
  const row = {
    profile: { socials: { value: { linkedin: "https://www.linkedin.com/company/example/" } } },
    passes: {
      context_dev: { status: "candidate", credits: 10, fields: { socials: [{ url: "https://linkedin.com/company/example" }] } },
      context_dev_checked: { checked: true, expected: { socials: ["https://linkedin.com/company/example"] } },
    },
  } as unknown as BaseRecord;
  assert.deepEqual(contextReport([row]).fields, [{ field: "socials", checked: 1, baseCorrect: 1, contextCorrect: 1 }]);
});

const batch = (over: Partial<BatchIn>): BatchIn => ({
  batch: "ATF FFL list Sep 2026 · HI",
  started: "2026-10-01T00:00:00Z",
  total: 106,
  done: 106,
  failed: 0,
  pending: 0,
  with_site: 25,
  with_email: 10,
  ...over,
});

const skill = (over: Partial<SkillIn>): SkillIn => ({
  id: "base.find_site",
  version: "1.7.0",
  agent: "base",
  state: "approved",
  description: "Pass 2. Find the business website.",
  approved_at: "2026-10-17T13:25:00Z",
  present: true,
  ...over,
});

test("totals add up across batches and skipped steps stay one combined count", () => {
  const model = buildModel({
    batches: [batch({ model_skipped: 4 }), batch({ batch: "NV", total: 612, done: 612, with_site: 431, with_email: 198, model_skipped: 0 })],
    skills: [],
    now: new Date("2026-10-17T15:40:00Z"),
  });
  assert.equal(model.totals.records, 718);
  assert.equal(model.totals.withSite, 456);
  assert.equal(model.totals.withEmail, 208);
  assert.equal(model.totals.skipped, 4);
  assert.equal(model.loadError, false);
  assert.equal(model.empty, false);
});

test("a missing skipped count is shown as not reported, never as zero", () => {
  const model = buildModel({ batches: [batch({})], skills: [], now: new Date() });
  assert.equal(model.totals.skipped, null);
  assert.equal(model.batches[0]?.skipped, null);
});

test("Tank down is an error, an empty list is empty", () => {
  assert.equal(buildModel({ batches: null, skills: null, now: new Date() }).loadError, true);
  assert.equal(buildModel({ batches: null, skills: null, now: new Date() }).skillsError, true);
  const empty = buildModel({ batches: [], skills: [], now: new Date() });
  assert.equal(empty.loadError, false);
  assert.equal(empty.empty, true);
});

test("batch status reads in plain words", () => {
  assert.equal(batchStatus(batch({ pending: 3 })), "Running");
  assert.equal(batchStatus(batch({ failed: 1 })), "Some failed");
  assert.equal(batchStatus(batch({ model_skipped: 2 })), "Skipped steps waiting");
  assert.equal(batchStatus(batch({})), "Done");
});

test("only approved Base skills are listed; a candidate never shows as in use", () => {
  const rows = approvedSkills([
    skill({}),
    skill({ version: "1.6.0", state: "retired" }),
    skill({ version: "1.8.0", state: "candidate" }),
    skill({ id: "ffl.profile", version: "1.1.0", agent: "base" }),
    skill({ id: "tier0.chat", version: "2.0.0", agent: "tier0" }),
  ]);
  assert.deepEqual(
    rows.map((row) => `${row.id}@${row.version}`),
    ["base.find_site@1.7.0", "ffl.profile@1.1.0"],
  );
  assert.equal(rows[0]?.label, "Find the website");
  assert.equal(rows[0]?.approvedOn, "17 Oct");
});

test("times read in Pacific time", () => {
  assert.equal(shortDate("2026-10-17T05:00:00Z"), "16 Oct");
  assert.equal(refreshedLabel(new Date("2026-10-17T15:40:00Z"), new Date("2026-10-17T16:00:00Z")), "Today, 8:40 AM PT");
  assert.equal(refreshedLabel(new Date("2026-10-16T15:40:00Z"), new Date("2026-10-17T16:00:00Z")), "16 Oct, 8:40 AM PT");
});
