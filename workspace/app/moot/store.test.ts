import assert from "node:assert/strict";
import { test } from "node:test";
import { getMatch, isPublicWatch, listPublishedMatches } from "./store";

test("unpublished watch is not public", () => {
  assert.equal(isPublicWatch("fixture-unpublished"), false);
  assert.equal(getMatch("fixture-unpublished")?.published, false);
});

test("published watch is public and has required sections", () => {
  const row = getMatch("fixture-published");
  assert.ok(row);
  assert.equal(isPublicWatch("fixture-published"), true);
  assert.ok((row!.transcript ?? []).length > 0);
  assert.ok((row!.judgmentReasons ?? []).length > 0);
  assert.ok(row!.reveal);
  assert.ok((row!.authorities ?? []).length > 0);
  assert.ok(row!.fairnessReading);
});

test("unknown match is not public", () => {
  assert.equal(getMatch("no-such"), null);
  assert.equal(isPublicWatch("no-such"), false);
});

test("listPublishedMatches returns only published fixtures", () => {
  const rows = listPublishedMatches();
  assert.ok(rows.some((row) => row.matchId === "fixture-published"));
  assert.ok(rows.every((row) => row.published));
  assert.ok(!rows.some((row) => row.matchId === "fixture-unpublished"));
});
