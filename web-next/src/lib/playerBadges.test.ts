import { describe, expect, it } from "vitest";

import { BADGES, badgeFromInjury, badgeFromTag, badgeLegend, badgesAriaLabel, contextSuppressed, resolveBadges } from "./playerBadges";

describe("playerBadges", () => {
  it("every badge is a glyph of at most two characters on an existing tone", () => {
    for (const b of Object.values(BADGES)) {
      expect([...b.glyph].length).toBeLessThanOrEqual(2);
      expect(["success", "danger", "warning", "muted", "accent", "action"]).toContain(b.tone);
      expect(b.label.length).toBeGreaterThan(1);
    }
  });
  it("sorts by severity, drops duplicates and suppressed kinds, and folds the rest into +n", () => {
    const r = resolveBadges([{ kind: "rookie" }, { kind: "bench" }, { kind: "out", detail: "2 wks" }, { kind: "out" }, { kind: "fa" }, { kind: "taxi" }], { suppress: ["fa"], max: 3 });
    expect(r.shown.map((b) => b.kind)).toEqual(["out", "taxi", "rookie"]);
    expect(r.overflow).toBe(1);
    expect(badgesAriaLabel(r)).toBe("Out: 2 wks, Taxi squad, Rookie, plus 1 more: Bench");
  });
  it("suppresses a badge that is true for every row of a list", () => {
    const rows = [["rookie"], ["rookie", "out"], ["rookie"]] as const;
    expect(contextSuppressed(rows)).toEqual(["rookie"]);
    expect(contextSuppressed([["rookie"], ["rookie"]])).toEqual([]);
    expect(contextSuppressed([["rookie"], [], ["rookie"]])).toEqual([]);
    expect(contextSuppressed([["out"], ["out"], ["out"]])).toEqual([]);
  });
  it("maps legacy tags and injury words, leaving non-status tags as text", () => {
    expect(badgeFromTag({ key: "rookie", label: "ROOKIE" })?.kind).toBe("rookie");
    expect(badgeFromTag({ key: "owner", label: "Free agent" })?.kind).toBe("fa");
    expect(badgeFromTag({ key: "owner", label: "Taco Tuesday" })).toBeNull();
    expect(badgeFromTag({ key: "block", label: "On block" })?.kind).toBe("block");
    expect(badgeFromTag({ key: "out", label: "Out 2w" })).toEqual({ kind: "out", detail: "2 wks" });
    expect(badgeFromTag({ key: "role", label: "Fill-in" })?.kind).toBe("fillin");
    expect(badgeFromInjury("Questionable")).toBe("questionable");
    expect(badgeFromInjury("IR")).toBe("ir");
    expect(badgeFromInjury("")).toBeNull();
  });
  it("lists the legend in severity order", () => {
    expect(badgeLegend()[0].kind).toBe("out");
    expect(badgeLegend(["bench", "rookie"]).map((b) => b.kind)).toEqual(["rookie", "bench"]);
  });
});
