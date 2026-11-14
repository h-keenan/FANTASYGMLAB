import { describe, expect, it } from "vitest";

import {
  CONNECT_PRIMARY_LABEL,
  CONNECT_TRUST_LINE,
  connectCtaLabel,
  connectWays,
  defaultLeagueSelection,
  groupLeaguesBySeason,
  leagueMeta,
  planSaves,
  summarizeSaves,
  toggleLeague,
} from "@/lib/connectFlow";

const L = (id: string, season: string, name = id) => ({ league_id: id, name, season, total_rosters: 12 });
const leagues = [L("a25", "2025"), L("b26", "2026"), L("c26", "2026"), L("d24", "2024")];

describe("connect flow", () => {
  it("has one primary label and a single-line trust copy", () => {
    expect(CONNECT_PRIMARY_LABEL).toBe("Connect");
    expect(CONNECT_TRUST_LINE).not.toContain("\n");
    expect(CONNECT_TRUST_LINE.length).toBeLessThan(90);
  });

  it("keeps every capability reachable: other platforms, account, sample; account hides once signed in", () => {
    expect(connectWays({ hasAccount: false }).map((w) => w.key)).toEqual(["espn", "fleaflicker", "mfl", "account", "sample"]);
    expect(connectWays({ hasAccount: true }).map((w) => w.key)).toEqual(["espn", "fleaflicker", "mfl", "sample"]);
  });

  it("groups by season newest first", () => {
    expect(groupLeaguesBySeason(leagues).map((g) => g.season)).toEqual(["2026", "2025", "2024"]);
  });

  it("preselects only the first league of the newest season", () => {
    expect(defaultLeagueSelection(leagues)).toEqual(["b26"]);
    expect(defaultLeagueSelection([])).toEqual([]);
  });

  it("toggles and labels the CTA", () => {
    expect(toggleLeague(["a"], "b")).toEqual(["a", "b"]);
    expect(toggleLeague(["a", "b"], "a")).toEqual(["b"]);
    expect(connectCtaLabel(0)).toBe("Pick a league");
    expect(connectCtaLabel(1)).toBe("Connect 1 league");
    expect(connectCtaLabel(3)).toBe("Connect 3 leagues");
    expect(leagueMeta(L("x", "2026"))).toBe("2026 · 12 teams");
  });

  it("plans saves newest first and makes only the first the default", () => {
    const plan = planSaves(["a25", "c26", "b26"], leagues);
    expect(plan.map((p) => [p.league.league_id, p.makeDefault])).toEqual([["b26", true], ["c26", false], ["a25", false]]);
  });

  it("summarizes: opens the first saved, flags the cap without blocking, reports other failures", () => {
    const s = summarizeSaves([
      { leagueId: "b26", leagueName: "B", ok: true, warming: true },
      { leagueId: "c26", leagueName: "C", ok: false, reason: "at_cap" },
      { leagueId: "a25", leagueName: "A", ok: false, reason: "league_not_found" },
    ]);
    expect(s).toEqual({ open: { leagueId: "b26", leagueName: "B", warming: true }, savedCount: 1, atCap: true, failedReason: "league_not_found" });
    expect(summarizeSaves([{ leagueId: "x", leagueName: "X", ok: false, reason: "at_cap" }]).open).toBeNull();
  });
});
