import assert from "node:assert/strict";
import { test } from "node:test";
import { reviewGate, SIGN_OFF_REFUSED, signOffRefusal } from "../workspace/app/review/founder.ts";

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

test("a founder can view both queues and cannot sign off", () => {
  const gate = reviewGate({
    userId: "user_founder",
    orgRole: "org:admin",
    adminIds: admins,
    jurisdiction: "",
    admissionNo: "",
  });
  assert.ok(gate);
  assert.deepEqual(gate.jurisdictions, ["us", "za"]);
  const founder = { founder: true, role: "admin", admissionNo: "", jurisdictions: gate.jurisdictions };
  assert.equal(signOffRefusal(founder, "us"), SIGN_OFF_REFUSED);
  assert.equal(signOffRefusal(founder, "za"), SIGN_OFF_REFUSED);
  assert.equal(signOffRefusal({
    founder: true,
    role: "org:reviewer",
    admissionNo: "12345",
    jurisdictions: ["us", "za"],
  }, "za"), SIGN_OFF_REFUSED);
});

test("a full reviewer can sign off in their jurisdiction", () => {
  const reviewer = { founder: false, role: "org:reviewer", admissionNo: "12345", jurisdictions: ["za"] };
  assert.equal(signOffRefusal(reviewer, "za"), null);
  assert.equal(signOffRefusal(reviewer, "us"), "You can only sign off work in your jurisdiction.");
  assert.equal(signOffRefusal({ ...reviewer, admissionNo: "" }, "za"), SIGN_OFF_REFUSED);
  assert.equal(signOffRefusal({ ...reviewer, role: "admin" }, "za"), SIGN_OFF_REFUSED);
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
