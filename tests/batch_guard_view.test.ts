import assert from "node:assert/strict";
import { test } from "node:test";
import { graduationReview } from "../workspace/app/tank/graduation-copy.ts";
import { entersPool, nextStatus, quarantineActions } from "../workspace/app/market-lab/quarantine.ts";

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

test("graduation names a model trained on removed data and a one-region drop", () => {
  assert.equal(graduationReview({ can_promote: true, trained_on_removed: true }), "trained on removed data");
  assert.equal(graduationReview({ can_promote: false, blocked_reason: "dropped" }), "Blocked: one region scored lower");
  assert.equal(graduationReview({ can_promote: true }), "Promote");
  assert.equal(graduationReview({ can_promote: false }), "More evidence needed");
});
