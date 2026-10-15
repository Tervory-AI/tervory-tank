import assert from "node:assert/strict";
import { test } from "node:test";
import { founderDenial, isListedFounder } from "../workspace/app/review/founder.ts";
import { headerLinks, usesOwnShell } from "../workspace/app/product-nav.ts";

test("a customer call is rejected", () => {
  const denied = founderDenial("user_customer", "user_founder, user_other");
  assert.deepEqual(denied, { error: "Not found", status: 404 });
});

test("a founder call is allowed", () => {
  assert.equal(founderDenial("user_founder", " user_founder , user_other "), null);
  assert.equal(isListedFounder("user_other", " user_founder , user_other "), true);
});

test("a blank list and a missing user are rejected", () => {
  assert.deepEqual(founderDenial("user_founder", ""), { error: "Not found", status: 404 });
  assert.deepEqual(founderDenial("user_founder", undefined), { error: "Not found", status: 404 });
  assert.deepEqual(founderDenial(null, "user_founder"), { error: "Not found", status: 404 });
  assert.deepEqual(founderDenial("", "user_founder"), { error: "Not found", status: 404 });
  assert.equal(isListedFounder("user_nope", "user_founder"), false);
});

test("the product header says Skala and the address is /skala", () => {
  const customer = headerLinks(false).map((link) => link.label);
  const founder = headerLinks(true).map((link) => link.label);
  assert.deepEqual(customer, ["Chat", "Tasks", "Data", "Ledger"]);
  assert.deepEqual(founder, ["Chat", "Tasks", "Data", "Skala", "Ledger", "Tank"]);
  assert.equal(headerLinks(true).find((link) => link.label === "Skala")?.href, "/skala");
  assert.equal(headerLinks(true).some((link) => link.href === "/skills"), false);
  assert.equal(headerLinks(true).find((link) => link.label === "Tank")?.href, "/tank");
});

test("sign-in, sign-up, and onboarding use their own shell", () => {
  for (const path of ["/sign-in", "/sign-in/", "/sign-in/factor-one", "/sign-up", "/sign-up/verify", "/onboarding", "/onboarding/"]) {
    assert.equal(usesOwnShell(path), true, path);
  }
  for (const path of ["/", "/tasks", "/data", "/skala", "/ledger", "/tank", "/admin", "/review"]) {
    assert.equal(usesOwnShell(path), false, path);
  }
});
