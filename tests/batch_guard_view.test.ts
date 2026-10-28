import assert from "node:assert/strict";
import { test } from "node:test";
import { graduationReview } from "../workspace/app/tank/graduation-copy.ts";
import {
  QUARANTINE_ERROR,
  entersPool,
  nextStatus,
  quarantineActionResult,
  quarantineFromResponse,
  quarantinePageError,
  quarantineActions,
} from "../workspace/app/market-lab/quarantine.ts";

test("a held batch can be released or rejected, and a rejected batch never enters the pool", () => {
  assert.deepEqual(quarantineActions("held"), ["Release", "Reject"]);
  assert.deepEqual(quarantineActions("pooled"), ["Remove"]);
  assert.deepEqual(quarantineActions("rejected"), []);
  assert.equal(nextStatus("held", "release"), "pooled");
  assert.equal(nextStatus("held", "reject"), "rejected");
  assert.equal(nextStatus("rejected", "release"), null);
  assert.equal(entersPool("pooled"), true);
  assert.equal(entersPool("held"), false);
  assert.equal(entersPool("rejected"), false);
  assert.equal(entersPool("removed"), false);
});

const held = {
  id: "batch-held",
  series_id: "zar.rand",
  series_name: "Rand",
  source: "fixture",
  region: "za",
  currency: "ZAR",
  unit: "rand",
  fetched_at: "2026-02-01T00:00:00Z",
  status: "held",
  reason: "jump",
};

test("a missing reply, an unreachable room, or a bad status changes nothing", () => {
  const page = [{ ...held, seriesName: "Rand", fetchedAt: held.fetched_at }];
  for (const status of [null, 401, 409, 500, 503]) {
    const loaded = quarantineFromResponse(status, { batches: [held] });
    assert.equal(loaded.error, QUARANTINE_ERROR);
    assert.deepEqual(loaded.batches, []);
    const acted = quarantineActionResult(status, page);
    assert.equal(acted.error, QUARANTINE_ERROR);
    assert.equal(acted.batches, page);
  }
  const broken = quarantineFromResponse(200, { batches: [{ status: "held" }] });
  assert.equal(broken.error, QUARANTINE_ERROR);
  assert.deepEqual(broken.batches, []);
  const ok = quarantineFromResponse(200, { batches: [held] });
  assert.equal(ok.error, null);
  assert.equal(ok.batches.length, 1);
  assert.equal(ok.batches[0].id, "batch-held");
  assert.equal(ok.batches[0].seriesName, "Rand");
  assert.equal("seriesId" in ok.batches[0], false);
  assert.equal(quarantineFromResponse(200, { batches: [{ ...held, series_name: undefined }] }).error, QUARANTINE_ERROR);
  assert.equal(quarantineActionResult(200, page).error, null);
  assert.equal(quarantineActionResult(200, page).batches, page);
  assert.equal(quarantinePageError(null, "1"), QUARANTINE_ERROR);
  assert.equal(quarantinePageError(null, ["1"]), QUARANTINE_ERROR);
  assert.equal(quarantinePageError(null, undefined), null);
  assert.equal(quarantinePageError(QUARANTINE_ERROR, undefined), QUARANTINE_ERROR);
});

test("graduation names a model trained on removed data and a one-region drop", () => {
  assert.equal(graduationReview({ can_promote: true, trained_on_removed: true }), "trained on removed data");
  assert.equal(graduationReview({ can_promote: false, blocked_reason: "dropped" }), "Blocked: one region scored lower");
  assert.equal(graduationReview({ can_promote: true }), "Promote");
  assert.equal(graduationReview({ can_promote: false }), "More evidence needed");
});
