import assert from "node:assert/strict";
import { test } from "node:test";
import { reviewGate } from "../workspace/app/review/founder.ts";

const admins = "user_founder, user_other";

test("a founder opens review without a reviewer role", () => {
  const gate = reviewGate({
    userId: "user_founder",
    orgRole: "org:admin",
    adminIds: admins,
    jurisdiction: "",
    admissionNo: "",
  });
  assert.equal(gate?.founder, true);
  assert.deepEqual(gate?.jurisdictions, ["us", "za"]);
});

test("a reviewer with an admission number and a jurisdiction opens review", () => {
  const gate = reviewGate({
    userId: "user_lawyer",
    orgRole: "org:reviewer",
    adminIds: admins,
    jurisdiction: "za",
    admissionNo: "12345",
  });
  assert.equal(gate?.founder, false);
  assert.equal(gate?.admissionNo, "12345");
  assert.deepEqual(gate?.jurisdictions, ["za"]);
});

test("a customer and an incomplete reviewer are refused", () => {
  assert.equal(reviewGate({
    userId: "user_customer",
    orgRole: "org:member",
    adminIds: admins,
    jurisdiction: "us",
    admissionNo: "1",
  }), null);
  assert.equal(reviewGate({
    userId: "user_lawyer",
    orgRole: "reviewer",
    adminIds: admins,
    jurisdiction: "",
    admissionNo: "",
  }), null);
  assert.equal(reviewGate({
    userId: null,
    orgRole: "org:reviewer",
    adminIds: admins,
    jurisdiction: "us",
    admissionNo: "1",
  }), null);
});
