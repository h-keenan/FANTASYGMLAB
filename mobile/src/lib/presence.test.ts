// Run with: node --experimental-strip-types --test src/lib/presence.test.ts
// Same cases as web-next's presence.test.ts: both platforms share the rules. (`expect` is a tiny shim.)
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

function expect(actual: any) {
  return {
    toBe: (v: any) => assert.equal(actual, v),
    toEqual: (v: any) => assert.deepEqual(actual, v),
    toBeNull: () => assert.equal(actual, null),
  };
}

import type { PresenceEntry } from "./presence.ts";
import {
  MAX_PRESENCE_ROWS,
  PRESENCE_ENTER_MS,
  PRESENCE_EXIT_MS,
  clampPresenceMs,
  collapseTargetPx,
  dropPresenceEntry,
  mergePresenceEntries,
  presenceDurations,
  presenceFrame,
  presenceMounted,
  presenceNext,
  presencePhaseMs,
  presenceSettle,
  presenceTarget,
  shouldAnimatePresenceList,
} from "./presence.ts";

// Run on both platforms (mobile/src/lib/presence.test.ts has the same cases): one set of rules.

describe("durations", () => {
  it("clamp to the 120-300ms motion vocabulary", () => {
    expect(clampPresenceMs(10)).toBe(120);
    expect(clampPresenceMs(500)).toBe(300);
    expect(clampPresenceMs(200)).toBe(200);
    expect(clampPresenceMs(undefined)).toBe(PRESENCE_ENTER_MS);
    expect(clampPresenceMs(Number.NaN, PRESENCE_EXIT_MS)).toBe(PRESENCE_EXIT_MS);
  });

  it("defaults: enter 240, exit 180; clamps what a caller asks for", () => {
    expect(presenceDurations(undefined, false)).toEqual({ enterMs: 240, exitMs: 180 });
    expect(presenceDurations({ enterMs: 50, exitMs: 999 }, false)).toEqual({ enterMs: 120, exitMs: 300 });
  });

  it("reduced motion makes both 0 whatever was asked", () => {
    expect(presenceDurations({ enterMs: 300, exitMs: 300 }, true)).toEqual({ enterMs: 0, exitMs: 0 });
  });
});

describe("phase machine", () => {
  const d = { enterMs: 240, exitMs: 180 };
  const none = { enterMs: 0, exitMs: 0 };

  it("show mounts and enters; hide exits and then unmounts", () => {
    expect(presenceNext("exited", true, d)).toBe("entering");
    expect(presenceSettle("entering")).toBe("entered");
    expect(presenceNext("entered", false, d)).toBe("exiting");
    expect(presenceMounted("exiting")).toBe(true);
    expect(presenceSettle("exiting")).toBe("exited");
    expect(presenceMounted("exited")).toBe(false);
  });

  it("a change mid-way reverses instead of waiting", () => {
    expect(presenceNext("exiting", true, d)).toBe("entering");
    expect(presenceNext("entering", false, d)).toBe("exiting");
  });

  it("no change leaves the phase alone", () => {
    expect(presenceNext("entered", true, d)).toBe("entered");
    expect(presenceNext("exited", false, d)).toBe("exited");
    expect(presenceNext("entering", true, d)).toBe("entering");
    expect(presenceNext("exiting", false, d)).toBe("exiting");
  });

  it("with zero durations (reduced motion) it appears and disappears at once", () => {
    expect(presenceNext("exited", true, none)).toBe("entered");
    expect(presenceNext("entered", false, none)).toBe("exited");
  });

  it("only the animating phases have a duration", () => {
    expect(presencePhaseMs("entering", d)).toBe(240);
    expect(presencePhaseMs("exiting", d)).toBe(180);
    expect(presencePhaseMs("entered", d)).toBe(0);
    expect(presencePhaseMs("exited", d)).toBe(0);
  });
});

describe("frames", () => {
  it("hidden vs shown per variant: opacity always, then a lift, a scale or a height", () => {
    expect(presenceFrame("fade", false)).toEqual({ opacity: 0, translateY: 0, scale: 1, openness: 1 });
    expect(presenceFrame("rise", false).translateY).toBe(8);
    expect(presenceFrame("pop", false).scale).toBe(0.94);
    expect(presenceFrame("collapse", false).openness).toBe(0);
    for (const v of ["fade", "rise", "pop", "collapse"] as const) expect(presenceFrame(v, true)).toEqual({ opacity: 1, translateY: 0, scale: 1, openness: 1 });
  });

  it("an enter starts hidden then goes shown; an exit goes hidden", () => {
    expect(presenceTarget("rise", "entering", false).opacity).toBe(0);
    expect(presenceTarget("rise", "entering", true).opacity).toBe(1);
    expect(presenceTarget("rise", "entered").opacity).toBe(1);
    expect(presenceTarget("rise", "exiting").opacity).toBe(0);
    expect(presenceTarget("collapse", "exited").openness).toBe(0);
  });

  it("the collapse height is the measured one, or null (natural height) when unmeasurable", () => {
    expect(collapseTargetPx(120.4)).toBe(120);
    expect(collapseTargetPx(0)).toBeNull();
    expect(collapseTargetPx(null)).toBeNull();
    expect(collapseTargetPx(Number.NaN)).toBeNull();
  });
});

describe("list rows", () => {
  const key = (n: { id: string }) => n.id;
  const mk = (...ids: string[]) => ids.map((id) => ({ id }));
  const entries = (...ids: string[]): PresenceEntry<{ id: string }>[] => ids.map((id) => ({ key: id, item: { id }, present: true }));

  it("a removed row stays in its place, marked leaving", () => {
    const merged = mergePresenceEntries(entries("a", "b", "c"), mk("a", "c"), key);
    expect(merged.map((e) => `${e.key}:${e.present}`)).toEqual(["a:true", "b:false", "c:true"]);
  });

  it("a removed first row stays first; a removed last row stays last", () => {
    expect(mergePresenceEntries(entries("a", "b"), mk("b"), key).map((e) => `${e.key}:${e.present}`)).toEqual(["a:false", "b:true"]);
    expect(mergePresenceEntries(entries("a", "b"), mk("a"), key).map((e) => `${e.key}:${e.present}`)).toEqual(["a:true", "b:false"]);
  });

  it("a new row is added where the items say", () => {
    expect(mergePresenceEntries(entries("a", "c"), mk("a", "b", "c"), key).map((e) => e.key)).toEqual(["a", "b", "c"]);
  });

  it("a leaving row that comes back is present again, in the item order", () => {
    const leaving = mergePresenceEntries(entries("a", "b"), mk("a"), key);
    const back = mergePresenceEntries(leaving, mk("a", "b"), key);
    expect(back.map((e) => `${e.key}:${e.present}`)).toEqual(["a:true", "b:true"]);
  });

  it("several removals keep their relative places; dropping an entry removes it", () => {
    const merged = mergePresenceEntries(entries("a", "b", "c", "d"), mk("a", "d"), key);
    expect(merged.map((e) => e.key)).toEqual(["a", "b", "c", "d"]);
    expect(dropPresenceEntry(merged, "b").map((e) => e.key)).toEqual(["a", "c", "d"]);
  });

  it("long lists do not animate", () => {
    expect(shouldAnimatePresenceList(MAX_PRESENCE_ROWS)).toBe(true);
    expect(shouldAnimatePresenceList(MAX_PRESENCE_ROWS + 1)).toBe(false);
    expect(shouldAnimatePresenceList(0)).toBe(false);
  });
});
