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

test("a founder can view and sign off in both jurisdictions", () => {
  const gate = reviewGate({
    userId: "user_founder",
    orgRole: "org:admin",
    adminIds: admins,
    jurisdiction: "za",
    admissionNo: "",
  });
  assert.ok(gate);
  assert.equal(gate.founder, true);
  assert.deepEqual(gate.jurisdictions, ["us", "za"]);
  const founder = { founder: true, role: "admin", admissionNo: "", jurisdictions: gate.jurisdictions };
  assert.equal(signOffRefusal(founder, "us"), null);
  assert.equal(signOffRefusal(founder, "za"), null);
});

test("a reviewer without an admission number is refused", () => {
  assert.equal(signOffRefusal({
    founder: false,
    role: "org:reviewer",
    admissionNo: "",
    jurisdictions: ["za"],
  }, "za"), SIGN_OFF_REFUSED);
  assert.equal(signOffRefusal({
    founder: false,
    role: "reviewer",
    admissionNo: "   ",
    jurisdictions: ["us"],
  }, "us"), SIGN_OFF_REFUSED);
});

test("a full reviewer can sign off in their own jurisdiction only", () => {
  const reviewer = { founder: false, role: "org:reviewer", admissionNo: "12345", jurisdictions: ["za"] };
  assert.equal(signOffRefusal(reviewer, "za"), null);
  assert.equal(signOffRefusal(reviewer, "us"), "You can only sign off work in your jurisdiction.");
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
