import { describe, expect, it } from "vitest";

import {
  DIRECTION_CHECKIN_INITIAL,
  directionChangedMessage,
  directionCheckinPrompt,
  directionCheckinReducer,
  directionSwitchLabel,
  type DirectionCheckinResponse,
  type DirectionCheckinState,
} from "./directionCheckin";

const SHOW: DirectionCheckinResponse = {
  ok: true,
  show: true,
  reason: "",
  moment: "midseason",
  moment_key: "2026:midseason",
  moment_label: "Midseason",
  week: 8,
  stance: "rebuilding",
  stance_label: "Rebuilding",
  options: [{ value: "competing", label: "Competing" }, { value: "balanced", label: "Balanced" }],
  headline: "Midseason: still Rebuilding?",
  body: "You are about halfway through. Does Rebuilding still describe your team?",
  keep_label: "Still fits",
  dismiss_label: "Not now",
};

describe("directionCheckinPrompt", () => {
  it("builds the card from a complete show answer", () => {
    expect(directionCheckinPrompt(SHOW)).toEqual({
      momentKey: "2026:midseason",
      stance: "rebuilding",
      stanceLabel: "Rebuilding",
      headline: "Midseason: still Rebuilding?",
      body: "You are about halfway through. Does Rebuilding still describe your team?",
      keepLabel: "Still fits",
      dismissLabel: "Not now",
      options: [{ value: "competing", label: "Competing" }, { value: "balanced", label: "Balanced" }],
    });
  });

  it("never shows on a quiet, partial or failed answer", () => {
    expect(directionCheckinPrompt(null)).toBeNull();
    expect(directionCheckinPrompt({ ok: true, show: false, reason: "no_moment" })).toBeNull();
    expect(directionCheckinPrompt({ ...SHOW, ok: false })).toBeNull();
    expect(directionCheckinPrompt({ ...SHOW, moment_key: "" })).toBeNull();
    expect(directionCheckinPrompt({ ...SHOW, headline: undefined })).toBeNull();
    expect(directionCheckinPrompt({ ...SHOW, stance: "" })).toBeNull();
  });

  it("falls back to default button words and drops malformed options", () => {
    const prompt = directionCheckinPrompt({ ...SHOW, keep_label: undefined, dismiss_label: undefined, stance_label: undefined, options: [{ value: "", label: "x" }, { value: "balanced", label: "Balanced" }] });
    expect(prompt).toMatchObject({ keepLabel: "Still fits", dismissLabel: "Not now", stanceLabel: "rebuilding", options: [{ value: "balanced", label: "Balanced" }] });
  });

  it("words the actions", () => {
    expect(directionSwitchLabel({ value: "competing", label: "Competing" })).toBe("Switch to Competing");
    expect(directionChangedMessage("Competing")).toMatch(/Direction set to Competing/);
  });
});

describe("directionCheckinReducer", () => {
  const ready = directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, { type: "loaded", response: SHOW });

  it("stays hidden unless the server says show", () => {
    expect(directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, { type: "loaded", response: null })).toEqual({ phase: "hidden" });
    expect(directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, { type: "loaded", response: { ok: true, show: false } })).toEqual({ phase: "hidden" });
    expect(ready.phase).toBe("ready");
  });

  it("nothing reopens a hidden card: not a second load, not a late response", () => {
    const hidden = directionCheckinReducer(directionCheckinReducer(ready, { type: "save" }), { type: "answered", action: "dismissed" });
    expect(hidden).toEqual({ phase: "hidden" });
    expect(directionCheckinReducer(hidden, { type: "loaded", response: SHOW })).toBe(hidden);
    const quiet = directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, { type: "loaded", response: null });
    expect(directionCheckinReducer(quiet, { type: "loaded", response: SHOW })).toBe(quiet);
    expect(directionCheckinReducer(ready, { type: "loaded", response: SHOW })).toBe(ready);
  });

  it("kept and dismissed hide it; a change shows one confirmation", () => {
    const saving = directionCheckinReducer(ready, { type: "save" });
    expect(saving.phase).toBe("saving");
    expect(directionCheckinReducer(saving, { type: "answered", action: "kept" })).toEqual({ phase: "hidden" });
    expect(directionCheckinReducer(saving, { type: "answered", action: "dismissed" })).toEqual({ phase: "hidden" });
    expect(directionCheckinReducer(saving, { type: "answered", action: "changed", label: "Competing" })).toEqual({ phase: "changed", label: "Competing" });
    expect(directionCheckinReducer(saving, { type: "answered", action: "changed" })).toEqual({ phase: "hidden" });
  });

  it("a failed direction change reopens the card with an error and can be retried", () => {
    const saving = directionCheckinReducer(ready, { type: "save" });
    const failed = directionCheckinReducer(saving, { type: "failed" }) as Extract<DirectionCheckinState, { phase: "ready" }>;
    expect(failed.phase).toBe("ready");
    expect(failed.error).toMatch(/Try again/);
    expect(directionCheckinReducer(failed, { type: "save" }).phase).toBe("saving");
  });

  it("ignores events that do not apply to the current phase", () => {
    for (const event of [{ type: "save" }, { type: "failed" }, { type: "answered", action: "kept" }] as const) {
      expect(directionCheckinReducer(DIRECTION_CHECKIN_INITIAL, event)).toBe(DIRECTION_CHECKIN_INITIAL);
    }
  });
});
