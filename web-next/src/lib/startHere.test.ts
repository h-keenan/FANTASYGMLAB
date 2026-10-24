import { describe, expect, it } from "vitest";

import {
  EMPTY_START_HERE_STATE,
  START_HERE_STEPS,
  markStartHereStepDone,
  parseStartHereState,
  shouldShowStartHere,
} from "./startHere";

const NOW = Date.parse("2026-10-23T00:00:00Z");
const DAY = 24 * 60 * 60 * 1000;

describe("startHere", () => {
  it("has the three steps in order", () => {
    expect(START_HERE_STEPS.map((s) => s.key)).toEqual(["matchup", "trade_hub", "waivers"]);
  });
  it("shows only for recent accounts", () => {
    expect(shouldShowStartHere(EMPTY_START_HERE_STATE, new Date(NOW - 2 * DAY).toISOString(), NOW)).toBe(true);
    expect(shouldShowStartHere(EMPTY_START_HERE_STATE, new Date(NOW - 30 * DAY).toISOString(), NOW)).toBe(false);
    expect(shouldShowStartHere(EMPTY_START_HERE_STATE, null, NOW)).toBe(false);
  });
  it("hides when dismissed or all done", () => {
    const created = new Date(NOW - DAY).toISOString();
    expect(shouldShowStartHere({ dismissed: true, done: [] }, created, NOW)).toBe(false);
    let state = EMPTY_START_HERE_STATE;
    for (const step of START_HERE_STEPS) state = markStartHereStepDone(state, step.key);
    expect(shouldShowStartHere(state, created, NOW)).toBe(false);
  });
  it("parses bad storage safely and drops unknown keys", () => {
    expect(parseStartHereState("{nope")).toEqual(EMPTY_START_HERE_STATE);
    expect(parseStartHereState(JSON.stringify({ done: ["waivers", "x", "waivers"] })).done).toEqual(["waivers"]);
  });
});
