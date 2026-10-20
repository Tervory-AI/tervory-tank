import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { founderDenial } from "../workspace/app/review/founder.ts";
import {
  applyApproval,
  confirmApprove,
  costLabel,
  founderActionRefusal,
  oneLine,
  scoreDate,
  scoreLabel,
  versionAction,
  visibleLibrary,
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
  assert.equal(costLabel({ rung: 1, task_type: "reason.brief" }), "uses a model");
  assert.equal(scoreLabel(null), "No score yet");
  assert.equal(scoreLabel("0.956"), "95.6%");
  assert.equal(scoreDate("2026-10-12T15:00:00Z"), "12 Oct 2026");
});

test("actions follow the version state", () => {
  assert.equal(versionAction({ state: "candidate", present: true }), "evals");
  assert.equal(versionAction({ state: "staging", present: true }), "approve");
  assert.equal(versionAction({ state: "approved", present: true }), "retire");
  assert.equal(versionAction({ state: "retired", present: true }), null);
  assert.equal(versionAction({ state: "candidate", present: false }), null);
  assert.equal(confirmApprove("base.find_site", "1.7.0"), "Approve base.find_site 1.7.0?");
});

test("approval retires the previous approved version", () => {
  const next = applyApproval([
    skill({ id: "base.extract", version: "2.0.0", agent: "base", state: "staging" }),
    skill({ id: "base.extract", version: "1.0.0", agent: "base", state: "approved" }),
    skill({ id: "base.extract", version: "0.9.0", agent: "base", state: "retired" }),
    skill({ id: "other.skill", version: "1.0.0", agent: "tiger", state: "approved" }),
  ], "base.extract", "2.0.0");
  assert.equal(next.find((row) => row.version === "2.0.0")?.state, "approved");
  assert.equal(next.find((row) => row.version === "1.0.0")?.state, "retired");
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
