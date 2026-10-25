/**
 * Autumbra Watch fixture shape — panel matches GhostPanel; ThreatPayload receipts are propose-only.
 * No live HF. Flags stay OFF.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  AUTUMBRA_WATCH_FIXTURE,
  isUsableGhostPanel,
  type AutumbraThreatReceipt,
} from "../workspace/app/admin/autumbra/watch-fixtures.ts";

const ALLOWED_ACTIONS = new Set(["propose_shield", "open_match", "write_brief", "handoff"]);
const ALLOWED_STATUSES = new Set(["propose_only", "burned", "awaiting_founder"]);

test("Watch fixture panel is a usable GhostPanel", () => {
  const { panel } = AUTUMBRA_WATCH_FIXTURE;
  assert.equal(isUsableGhostPanel(panel), true);
  assert.equal(panel.monitor.running, true);
  assert.ok(panel.monitor.unavailable_checks >= 0);
  assert.ok(panel.incidents.length >= 2, "fixture should include Look-style investigations");
  for (const incident of panel.incidents) {
    assert.ok(incident.id);
    assert.ok(incident.target);
    assert.ok(incident.signal);
    assert.ok(Array.isArray(incident.steps));
    assert.ok(incident.steps.length >= 1, "each investigation needs receipts");
    for (const step of incident.steps) {
      assert.ok(step.ledger_id);
      assert.equal(typeof step.cost_usd, "number");
    }
  }
});

test("Watch fixture exposes ThreatPayload / advisory receipts (propose-only)", () => {
  const { threatReceipts } = AUTUMBRA_WATCH_FIXTURE;
  assert.ok(threatReceipts.length >= 1);
  for (const receipt of threatReceipts as AutumbraThreatReceipt[]) {
    assert.equal(receipt.schema_version, "ghost.threat.v1");
    assert.ok(ALLOWED_ACTIONS.has(receipt.action), receipt.action);
    assert.ok(ALLOWED_STATUSES.has(receipt.status), receipt.status);
    assert.notEqual(receipt.status, "enforced");
    assert.ok(receipt.target);
    assert.ok(receipt.summary);
    assert.ok(!/ghost|wraith/i.test(receipt.summary), "user-facing summary must not say Ghost/Wraith");
  }
  const connect = threatReceipts.find((r) => r.id === "fixture-match-autumbra-connect-001");
  assert.ok(connect, "CONNECT dogfood match should be mirrored into panel receipts");
  assert.equal(connect.action, "propose_shield");
  assert.equal(connect.status, "propose_only");
  assert.ok(connect.cve_ids?.includes("CVE-2026-55555"));
});

test("no Demo/Practice/fixture-banner chrome in Watch panel UI", async () => {
  const { readFile } = await import("node:fs/promises");
  const panel = await readFile(new URL("../workspace/app/admin/autumbra/panel.tsx", import.meta.url), "utf8");
  assert.ok(!/fixtureBanner|autumbra-fixture-banner/.test(panel));
  assert.ok(!/Demo|Practice|demo data|fixture banner/i.test(panel));
  // Code paths may mention GhostPanel types; ban only user-facing product nicknames in copy strings.
  assert.ok(!/Ghost(?!Panel|Incident|Result)|Wraith/.test(panel.replace(/GhostPanel|GhostIncident|GhostResult/g, "")));
});

test("isUsableGhostPanel rejects null and incomplete payloads", () => {
  assert.equal(isUsableGhostPanel(null), false);
  assert.equal(isUsableGhostPanel(undefined), false);
  assert.equal(isUsableGhostPanel({} as never), false);
  assert.equal(
    isUsableGhostPanel({
      incidents: [],
      monitor: { running: true, unavailable_checks: 0 },
      integrations: {},
    }),
    true,
  );
});
