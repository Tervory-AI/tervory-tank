import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  COST_LINES,
  COST_NOTE,
  MAX_BYTES,
  MSG,
  autoMap,
  batchName,
  canStart,
  dataPath,
  describePasses,
  fileIssue,
  industryLabel,
  issuesFor,
  parseCsv,
  passState,
  plainRunError,
  progressLine,
  toCsv,
} from "../../workspace/app/onboarding/csv.ts";

function source(rel: string): string {
  return readFileSync(new URL(rel, import.meta.url), "utf8");
}

test("fixture CSV auto-maps and shows that only the first rows are the preview", () => {
  const text = readFileSync(new URL("../e2e/fixtures/clients.csv", import.meta.url), "utf8");
  const table = parseCsv(text);
  assert.equal(table.rows.length, 6);
  const mapping = autoMap(table.headers);
  assert.deepEqual(mapping, { name: 0, address: 1, city: 2, state: 3, zip: 4, phone: 5, website: null });
  assert.equal(canStart(issuesFor(table, mapping)), true);
  assert.equal(table.rows.slice(0, 5).some((row) => row[0] === "Bay Tools"), false);
  assert.equal(table.rows[5][0], "Bay Tools");
  const csv = toCsv(table, mapping);
  assert.match(csv, /^name,address,city,state,zip,phone\n/);
  assert.match(csv, /Acme Guns/);
  assert.match(csv, /Bay Tools/);
  assert.equal(batchName("clients.csv"), "clients");
  assert.equal(dataPath("clients"), "/data?batch=clients");
});

test("synonyms, quotes, and a byte-order mark", () => {
  const table = parseCsv(
    "\uFEFFBusiness Name,Premise Street,City,State,ZIP Code,Voice Phone\r\n" +
      '"Acme, Inc.","123 Main St, Suite 4",Boston,MA,02110,617-555-0100\r\n',
  );
  const mapping = autoMap(table.headers);
  assert.equal(mapping.name, 0);
  assert.equal(mapping.address, 1);
  assert.equal(mapping.zip, 4);
  assert.equal(mapping.phone, 5);
  const csv = toCsv(table, mapping);
  assert.match(csv, /"Acme, Inc."/);
  assert.match(csv, /"123 Main St, Suite 4"/);
  assert.equal(canStart(issuesFor(table, mapping)), true);
});

test("validation stays in plain English and does not build a start while the file is wrong", () => {
  assert.equal(fileIssue({ name: "list.csv", size: MAX_BYTES + 1 }), MSG.tooBig);
  assert.equal(fileIssue({ name: "list.xlsx", size: 20 }), MSG.spreadsheet);
  assert.equal(fileIssue({ name: "notes.pdf", size: 20, type: "application/pdf" }), MSG.notCsv);
  assert.equal(fileIssue({ name: "empty.csv", size: 0 }), MSG.empty);
  assert.equal(fileIssue({ name: "ok.csv", size: 12 }), null);

  const missing = parseCsv("city,state\nBoston,MA\n");
  const missingMap = autoMap(missing.headers);
  const missingIssues = issuesFor(missing, missingMap);
  assert.equal(canStart(missingIssues), false);
  assert.ok(missingIssues.some((issue) => issue.message === MSG.needName));

  const emptyRow = parseCsv("name,city,state\nAcme,Boston,MA\n\nHarbor,Portland,ME\n");
  const emptyMap = autoMap(emptyRow.headers);
  const emptyIssues = issuesFor(emptyRow, emptyMap);
  assert.match(emptyIssues.map((issue) => issue.message).join(" "), /Row 3 is empty/);
  assert.equal(canStart(emptyIssues), true);
  const csv = toCsv(emptyRow, emptyMap);
  assert.match(csv, /Acme/);
  assert.match(csv, /Harbor/);
  assert.equal(csv.trim().split("\n").length, 3);

  const noPlace = parseCsv("name,phone\nAcme,617-555-0100\n");
  const noPlaceIssues = issuesFor(noPlace, autoMap(noPlace.headers));
  assert.equal(canStart(noPlaceIssues), false);
  assert.ok(noPlaceIssues.some((issue) => issue.message === MSG.needPlace));

  const blankName = parseCsv("name,city\n,Boston\n");
  const blankIssues = issuesFor(blankName, autoMap(blankName.headers));
  assert.match(blankIssues.map((issue) => issue.message).join(" "), /Row 2 has no business name/);
  assert.equal(canStart(blankIssues), false);
  assert.equal(issuesFor(parseCsv(""), null)[0].message, MSG.noHeader);
  assert.equal(issuesFor(parseCsv("name,city\n"), autoMap(["name", "city"]))[0].message, MSG.noRows);
});

test("costs are plain and paid search is the cheapest available", () => {
  assert.equal(COST_LINES.filter((line) => line.cost === "Free").length, 9);
  assert.match(COST_LINES.find((line) => line.id === "2a")?.cost ?? "", /cheapest paid search/);
  assert.match(COST_NOTE, /Nothing waits for approval/);
  assert.equal(industryLabel("ffl"), "Firearms dealers");
});

test("live progress is counted per pass", () => {
  const waiting = passState([], "1a");
  assert.equal(waiting.state, "waiting");
  const running = [
    { status: "running", passes: { "1a": { skill: "base.normalize" } } },
    { status: "queued", passes: {} },
  ];
  assert.equal(passState(running, "1a").state, "working");
  assert.equal(passState(running, "1a").have, 1);
  const done = running.map((row) => ({ status: "done", passes: { "1a": {}, "2b": {} } }));
  assert.equal(passState(done, "1a").state, "done");
  assert.equal(passState(done, "2a").state, "skipped");
  assert.equal(describePasses(done).length, 10);
  assert.equal(progressLine({ total: 6, done: 1, failed: 0, pending: 5 }, done), "6 records · 1 enriched · 5 still going");
});

test("run errors do not leak Tank internals", () => {
  assert.equal(plainRunError("Tank /v1/base/run 502: postgres://tank:secret@db/tank"), MSG.runFailed);
  assert.equal(plainRunError("no rows found; first line must be a header"), "no rows found; first line must be a header");
  assert.equal(dataPath("First batch"), "/data?batch=First%20batch");
});

test("onboarding stays on the allowed calls and the home page redirects new organizations", () => {
  const page = source("../../workspace/app/onboarding/page.tsx");
  const home = source("../../workspace/app/page.tsx");
  const tenant = source("../../workspace/lib/tenant.ts");
  const wizard = source("../../workspace/app/onboarding/wizard.tsx");
  assert.match(page, /preview:\s*false/);
  assert.match(page, /split_by_state:\s*false/);
  assert.equal(page.split('method: "POST"').length, 2);
  assert.match(home, /\/onboarding\/status/);
  assert.match(home, /router\.replace\("\/onboarding"\)/);
  assert.match(tenant, /export async function activeTenant/);
  assert.doesNotMatch(tenant, /activeTenant[\s\S]*createOrganization/);
  for (const file of [page, home, wizard, tenant]) {
    assert.doesNotMatch(file, /TANK_API_KEY|LITELLM|sk_live|sk_test/);
  }
  assert.match(wizard, /Nothing is uploaded until you press Start/);
  assert.match(wizard, /dataPath\(liveBatch\)/);
});
