import { describe, expect, it } from "vitest";

import {
  bottomTabAriaLabel,
  moreBadgeSummary,
  moreBadgeTotal,
  nextFooterScroll,
  pillPrimaryCompact,
  selectionActionLabel,
  selectionPrimary,
  isSelectionAction,
} from "./bottomNav";
import { simMoreBadgeSources } from "./simNotifications";

describe("selection mode", () => {
  const fallback = { key: "new", label: "New", onPress: () => {} };
  it("becomes the submit while something is selected and reverts when cleared", () => {
    const p = selectionPrimary({ count: 3, verb: "Find trades", onPress: () => {}, busy: true, fallback });
    expect(p?.label).toBe("3 selected · Find trades");
    expect(p?.busy).toBe(true);
    expect(isSelectionAction(p)).toBe(true);
    expect(selectionPrimary({ count: 0, verb: "Find trades", onPress: () => {}, fallback })).toBe(fallback);
    expect(selectionPrimary({ count: 0, verb: "x", onPress: () => {} })).toBeUndefined();
    expect(selectionActionLabel(1, "Analyze trade")).toBe("1 selected · Analyze trade");
  });
  it("never collapses to the icon form", () => {
    const primary = selectionPrimary({ count: 2, verb: "Find trades", glyph: "finder", onPress: () => {} });
    const tabs = ["a", "b", "c", "d"].map((k) => ({ key: k, label: k }));
    expect(pillPrimaryCompact({ tabs, primary }, 300)).toBe(false);
  });
});

describe("hide on scroll", () => {
  const run = (ys: number[], pinned = false) => {
    let st: ReturnType<typeof nextFooterScroll> = { hidden: false, lastY: ys[0], anchorY: ys[0], dir: 0 };
    for (const y of ys.slice(1)) st = nextFooterScroll(st, y, pinned);
    return st.hidden;
  };
  it("hides after scrolling down past the threshold and returns on scrolling up", () => {
    expect(run([100, 104])).toBe(false);
    expect(run([100, 130, 200])).toBe(true);
    expect(run([100, 200, 400, 390])).toBe(true);
    expect(run([100, 200, 400, 380])).toBe(false);
  });
  it("stays visible near the top and while pinned by a selection", () => {
    expect(run([10, 30, 40])).toBe(false);
    expect(run([100, 200, 400], true)).toBe(false);
  });
});

describe("More badge", () => {
  it("sums its sources and says what they are", () => {
    const src = { waiverResults: 2, rosterInjuries: 1, simWeekReady: 1 };
    expect(moreBadgeTotal(src)).toBe(4);
    expect(moreBadgeSummary(src)).toBe("2 waiver results, 1 new injury, Sim week ready");
    expect(moreBadgeTotal({})).toBe(0);
    expect(bottomTabAriaLabel({ label: "More", badge: 4, badgeSummary: moreBadgeSummary(src) })).toBe("More, 2 waiver results, 1 new injury, Sim week ready");
  });
  it("derives sources from unread sim notifications", () => {
    const item = (seq: number, kind: string) => ({ id: `${kind}${seq}`, seq, week: 1, kind, icon: "x", headline: "h", target: { screen: "home" as const } });
    const items = [item(5, "claim_won"), item(4, "claim_lost"), item(3, "injury"), item(2, "recap"), item(1, "injury")];
    expect(simMoreBadgeSources(items, 1)).toEqual({ waiverResults: 2, rosterInjuries: 1, simWeekReady: 1 });
    expect(simMoreBadgeSources(items, 9)).toEqual({ waiverResults: 0, rosterInjuries: 0, simWeekReady: 0 });
  });
});
