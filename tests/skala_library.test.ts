import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { founderDenial } from "../workspace/app/review/founder.ts";
import {
  applyApproval,
  approvalRowText,
  confirmApprove,
  tankRefusal,
  costLabel,
  founderActionRefusal,
  oneLine,
  scoreDate,
  scoreLabel,
  versionAction,
  visibleLibrary,
  versionSections,
  type LibrarySkill,
} from "../workspace/app/skala/library.ts";

function skill(partial: Partial<LibrarySkill> & Pick<LibrarySkill, "id" | "version" | "agent" | "state">): LibrarySkill {
  return {
    rung: 3,
    task_type: null,
    description: "Finds a site.",
    last_eval_score: null,
    last_eval_at: null,
    present: true,
    ...partial,
  };
}

test("skills group under their agent, with tier0 under Tank", () => {
  const groups = visibleLibrary([
    skill({ id: "base.find_site", version: "1.0.0", agent: "base", state: "approved", description: "Finds a site." }),
    skill({ id: "reason.brief", version: "1.0.0", agent: "tier0", state: "candidate", description: "A short brief.", rung: 1, task_type: "reason.brief" }),
    skill({ id: "tiger.price_extract", version: "1.1.0", agent: "tiger", state: "staging" }),
    skill({ id: "tiger.price_extract", version: "1.0.0", agent: "tiger", state: "retired" }),
  ], "", "", "");
  assert.deepEqual(groups.map((group) => group.label), ["Base", "Tiger", "Tank"]);
  assert.equal(groups[0]?.logo, "/brand/base-on-dark.png");
  assert.equal(groups[1]?.skills[0]?.versions[0]?.version, "1.1.0");
  assert.equal(groups[2]?.logo, "/brand/tank-on-dark.png");
  assert.ok((groups[0]?.logoHeight ?? 0) >= 40);
});

test("search and filters keep only matching versions", () => {
  const rows = [
    skill({ id: "base.find_site", version: "1.7.0", agent: "base", state: "approved", description: "Finds a business website." }),
    skill({ id: "base.normalize", version: "1.0.0", agent: "base", state: "candidate", description: "Cleans a record." }),
    skill({ id: "zenas.draft", version: "1.0.0", agent: "zenas", state: "approved", description: "Builds a contract." }),
  ];
  const searched = visibleLibrary(rows, "website", "", "");
  assert.deepEqual(searched.map((group) => group.skills.map((item) => item.id)), [["base.find_site"]]);
  const staged = visibleLibrary(rows, "", "base", "candidate");
  assert.equal(staged[0]?.skills[0]?.id, "base.normalize");
  assert.equal(visibleLibrary(rows, "missing", "", "").length, 0);
});

test("descriptions stay on one line and code skills say no model", () => {
  assert.equal(oneLine("  Finds a site.\n  Uses the name.  "), "Finds a site. Uses the name.");
  assert.equal(costLabel({ rung: 3, task_type: null }), "no model");
  assert.equal(costLabel({ rung: 3, task_type: null, calls_30d: 4, avg_cost_usd: 1.2 }), "no model");
  assert.equal(
    costLabel({ rung: 1, task_type: "reason.brief", calls_30d: 40, avg_cost_usd: 0.0031 }),
    "uses a model · $0.0031/call (30 days)",
  );
  assert.equal(
    costLabel({ rung: 1, task_type: "reason.brief", calls_30d: 0, avg_cost_usd: null }),
    "uses a model · no calls yet",
  );
  assert.equal(costLabel({ rung: 3, task_type: "market.research" }), "uses a model · no calls yet");
  assert.equal(
    costLabel({ rung: 1, task_type: "reason.brief", calls_30d: 2, avg_cost_usd: "0.000012" }),
    "uses a model · $0.000012/call (30 days)",
  );
  assert.equal(scoreLabel(null), "No score yet");
  assert.equal(scoreLabel("0.956"), "95.6%");
  assert.equal(scoreDate("2026-10-12T15:00:00Z"), "12 Oct 2026");
});

test("actions follow the version state", () => {
  assert.equal(versionAction({ state: "candidate", present: true }), "evals");
  assert.equal(versionAction({ state: "staging", present: true }), "approve");
  assert.equal(versionAction({ state: "approved", present: true }), "evals");
  assert.equal(versionAction({ state: "retired", present: true }), null);
  assert.equal(versionAction({ state: "candidate", present: false }), null);
  assert.equal(confirmApprove("base.find_site", "1.7.0"), "Approve base.find_site 1.7.0?");
});

test("approval keeps the previous approved version in staging during probation", () => {
  const next = applyApproval([
    skill({ id: "base.extract", version: "2.0.0", agent: "base", state: "staging" }),
    skill({ id: "base.extract", version: "1.0.0", agent: "base", state: "approved" }),
    skill({ id: "base.extract", version: "0.9.0", agent: "base", state: "retired" }),
    skill({ id: "other.skill", version: "1.0.0", agent: "tiger", state: "approved" }),
  ], "base.extract", "2.0.0");
  assert.equal(next.find((row) => row.version === "2.0.0")?.state, "approved");
  assert.equal(next.find((row) => row.version === "1.0.0")?.state, "staging");
  assert.equal(next.find((row) => row.version === "0.9.0")?.state, "retired");
  assert.equal(next.find((row) => row.id === "other.skill")?.state, "approved");
});

test("Approve is refused for a non-founder", () => {
  assert.deepEqual(founderActionRefusal(false), { error: "Not found", status: 404 });
  assert.equal(founderActionRefusal(true), null);
  assert.deepEqual(founderDenial("user_customer", "user_founder"), { error: "Not found", status: 404 });
  assert.equal(founderDenial("user_founder", "user_founder, user_other"), null);
  const route = readFileSync(new URL("../workspace/app/api/skala/route.ts", import.meta.url), "utf8");
  const post = route.slice(route.indexOf("export async function POST"));
  assert.ok(post.indexOf("deny()") < post.indexOf('action === "approve"'));
  assert.ok(route.indexOf("rejectUnlessFounder()") < route.indexOf("approveSkill("));
  const page = readFileSync(new URL("../workspace/app/skala/page.tsx", import.meta.url), "utf8");
  assert.ok(page.indexOf("rejectUnlessFounder()") < page.indexOf("listSkills()"));
  assert.ok(page.indexOf("notFound()") < page.indexOf("<SkalaApp"));
});

test("approving a zenas skill with no 50 of 50 shows the refusal on the row", () => {
  const sentence = "This Zenas skill stays unapproved. The made-up-case test has not run on this box through answer_question.";
  const thrown = `Tank /v1/skala/zenas.cite_check/1.0.0/approve 409: ${JSON.stringify({ detail: sentence })}`;
  const refused = tankRefusal(thrown);
  assert.ok(refused);
  assert.equal(refused.status, 409);
  assert.equal(refused.error, sentence);
  assert.equal(approvalRowText(refused.status, refused.error), sentence);
  const short = "This Zenas skill stays unapproved. The latest made-up-case test on this box is 49 of 50, not 50 of 50 through answer_question.";
  assert.equal(tankRefusal(`Tank /v1/skala/zenas.scope/1.0.0/approve 409: ${JSON.stringify({ detail: short })}`)?.error, short);
  assert.equal(approvalRowText(409, thrown), null);
  assert.equal(approvalRowText(502, sentence), null);
  const route = readFileSync(new URL("../workspace/app/api/skala/route.ts", import.meta.url), "utf8");
  const post = route.slice(route.indexOf("export async function POST"));
  assert.ok(post.includes("tankRefusal"));
  assert.ok(post.includes("status: refused.status"));
  const view = readFileSync(new URL("../workspace/app/skala/view.tsx", import.meta.url), "utf8");
  const row = view.slice(view.indexOf('className="sk-version"'), view.indexOf('className="sk-cases"'));
  const approveAt = row.indexOf("Approve");
  const messageAt = row.indexOf("sk-row-err");
  assert.ok(approveAt >= 0 && messageAt > approveAt);
  assert.ok(row.includes("rowRefusal.text"));
  assert.ok(row.includes("approvalRowText") === false);
  assert.ok(view.includes("approvalRowText"));
});

test("one skill keeps approved and newest pending visible with collapsed history", () => {
  const row = skill({id: "base.find_site", version: "1.7.0", agent: "base", state: "approved"});
  const versions = [
    {...row, version: "1.5.0", state: "candidate"},
    {...row, version: "1.7.0", state: "approved"},
    {...row, version: "1.8.0", state: "staging"},
    {...row, version: "1.6.0", state: "retired"},
  ];
  const sections = versionSections(versions);
  assert.deepEqual(sections.current.map(v => v.version), ["1.7.0", "1.8.0"]);
  assert.deepEqual(sections.history.map(v => v.version), ["1.6.0", "1.5.0"]);
});
