import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PRACTICE_SHIELD_ID,
  applyFixtureTap,
  fixtureBoard,
  isFixtureShield,
  resetFixtureStore,
} from "../workspace/app/admin/autumbra/shields-fixtures.ts";

test("fixture board is dry_run with at least one proposed shield", () => {
  resetFixtureStore();
  const board = fixtureBoard();
  assert.equal(board.tile.mode, "dry_run");
  assert.equal(board.tile.fixture, true);
  assert.ok(board.tile.open_total >= 1);
  assert.ok(board.shields.length >= 1);
  const practice = board.shields.find((s) => s.id === PRACTICE_SHIELD_ID);
  assert.ok(practice);
  assert.equal(practice.state, "proposed");
  assert.equal(isFixtureShield(PRACTICE_SHIELD_ID), true);
});

test("raise on fixture yields dry_run and does not arm live apply", () => {
  resetFixtureStore();
  const raised = applyFixtureTap(PRACTICE_SHIELD_ID, "raise");
  assert.equal(raised.state, "dry_run");
  assert.match(raised.note ?? "", /nothing was changed/i);
  assert.ok(raised.receipts.some((r) => r.status === "dry_run"));
});

test("undo on fixture yields withdrawn", () => {
  resetFixtureStore();
  applyFixtureTap(PRACTICE_SHIELD_ID, "raise");
  const undone = applyFixtureTap(PRACTICE_SHIELD_ID, "undo");
  assert.equal(undone.state, "withdrawn");
  assert.match(undone.note ?? "", /Nothing was changed/i);
});

test("unknown fixture id throws", () => {
  resetFixtureStore();
  assert.throws(() => applyFixtureTap("b2222222-2222-4222-8222-222222222222", "raise"));
});
