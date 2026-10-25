import assert from "node:assert/strict";
import { test } from "node:test";
import { founderDenial, isListedFounder } from "../workspace/app/review/founder.ts";
import { sidebarLabels, squadMembers, usesOwnShell } from "../workspace/app/product-nav.ts";

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

test("the sidebar keeps Billing, and Skala and Tank stay in the founder squad list", () => {
  const customer = sidebarLabels("/ledger", false, false);
  const founder = sidebarLabels("/ledger", true, false);
  assert.equal(customer.includes("Billing"), true);
  assert.equal(customer.includes("Skala"), false);
  assert.equal(customer.includes("Tank"), false);
  assert.equal(founder.includes("Skala"), false);
  assert.equal(founder.includes("Tank"), false);
  assert.equal(squadMembers(true).find((member) => member.label === "Skala")?.href, "/skala");
  assert.equal(squadMembers(true).find((member) => member.label === "Tank")?.href, "/tank");
  assert.equal(squadMembers(false).some((member) => member.label === "Skala"), false);
  assert.equal(squadMembers(false).some((member) => member.label === "Tank"), false);
  assert.ok(customer.indexOf("Dashboard") < customer.indexOf("Squad"));
  assert.ok(customer.indexOf("Squad") < customer.indexOf("Ledger"));
});

test("auth and squad product roots skip the workspace shell; shared pages keep it", () => {
  for (const path of ["/sign-in", "/sign-in/", "/sign-in/factor-one", "/sign-up", "/sign-up/verify", "/base", "/tiger", "/market-lab", "/market-lab/", "/rig", "/tisan", "/radix", "/zenas", "/skala", "/tank"]) {
    assert.equal(usesOwnShell(path), true, path);
  }
  for (const path of ["/", "/tasks", "/data", "/ledger", "/billing", "/admin", "/review", "/onboarding", "/onboarding/", "/prices", "/matters", "/zenas/feeds", "/skala/gold"]) {
    assert.equal(usesOwnShell(path), false, path);
  }
});
