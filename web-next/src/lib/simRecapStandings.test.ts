import { describe, expect, it } from "vitest";

import type { SimWeekRecap } from "./simGame";
import { simMovementText, simRecapPageKeys, simRecapPageTitle, simRecapStandingsModel } from "./simRecapStory";
import { SIM_TEAM_SIZES, simTeamNameFit } from "./simTeamIdentity";

const row = (rank: number, id: string, delta: number | null, over: Record<string, unknown> = {}) => ({
  rank, team_id: id, name: `Team ${id}`, is_you: id === "t5", wins: 10 - rank, losses: rank, ties: 0, pf: 1000 - rank, pa: 900, rank_delta: delta, ...over,
});
function recap(over: Partial<SimWeekRecap> = {}): SimWeekRecap {
  return {
    week: 6, kind: "regular", round: null,
    your_game: { opponent_id: "t2", opponent_name: "Snap Crackle Pop", your_pts: 118.1, opp_pts: 125.4, result: "loss", starters: [], optimal_pts: 130 },
    scores: [{ home: "t1", away: "t2", home_pts: 1, away_pts: 2, winner: "t2" }],
    standings: Array.from({ length: 12 }, (_, i) => row(i + 1, `t${i + 1}`, i === 4 ? 2 : i === 5 ? -1 : i === 6 ? 0 : null)),
    injuries: [], season_complete: false, champion: null, next_week: 7,
    ...over,
  } as unknown as SimWeekRecap;
}
const facts = { youId: "t5", playoffTeams: 6, names: {}, lineupWarnings: 0, offers: 0 };

describe("standings page", () => {
  it("sits after League and before Next, regular season only", () => {
    const keys = simRecapPageKeys(recap(), facts);
    expect(keys.indexOf("standings")).toBe(keys.indexOf("league") + 1);
    expect(keys.indexOf("standings")).toBeLessThan(keys.indexOf("next"));
    expect(simRecapPageKeys(recap({ kind: "playoff" }), facts)).not.toContain("standings");
    expect(simRecapPageKeys(recap({ standings: [] }), facts)).not.toContain("standings");
  });

  it("marks in / bubble / out around the cut and numbers seeds 1..N", () => {
    const m = simRecapStandingsModel(recap(), facts);
    expect(m.rows.map((r) => r.status)).toEqual(["in", "in", "in", "in", "in", "bubble", "bubble", "out", "out", "out", "out", "out"]);
    expect(m.rows.filter((r) => r.seed != null).map((r) => r.seed)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("compact = top 6, you and the cut neighbours, in rank order; your hero line says seed and movement", () => {
    const other = recap({ standings: recap().standings!.map((r) => ({ ...r, is_you: r.team_id === "t11" })) });
    const m = simRecapStandingsModel(other, { ...facts, youId: "t11" });
    expect(m.compact.map((r) => r.rank)).toEqual([1, 2, 3, 4, 5, 6, 7, 11]);
    const mine = simRecapStandingsModel(recap(), facts);
    expect(mine.caption).toBe("Seed 5, up 2");
    expect(m.caption).toBe("Outside the cut");
  });

  it("movement: up, down, no change, none (week 1 / old save without data)", () => {
    expect(simMovementText(2)).toBe("▲2");
    expect(simMovementText(-1)).toBe("▼1");
    expect(simMovementText(0)).toBe("–");
    expect(simMovementText(null)).toBe("");
    const m = simRecapStandingsModel(recap(), facts);
    expect(m.rows[4].delta).toBe(2);
    expect(m.rows[0].delta).toBeNull();
  });
});

describe("simRecapPageTitle", () => {
  it("has one big title per page and a result subtitle", () => {
    const r = recap();
    expect(simRecapPageTitle("result", r).title).toBe("Matchup Result");
    expect(simRecapPageTitle("result", r).subtitle).toBe("You lost by 7.3 to Snap Crackle Pop");
    expect(simRecapPageTitle("result", r).eyebrow).toBe("Week 6 recap");
    expect(simRecapPageTitle("matchup", r).title).toBe("How You Scored");
    expect(simRecapPageTitle("injuries", r).title).toBe("Injuries & Lineup");
    expect(simRecapPageTitle("league", r).title).toBe("Around the League");
    expect(simRecapPageTitle("standings", r).title).toBe("Standings");
    expect(simRecapPageTitle("next", r).title).toBe("Next Week");
    expect(simRecapPageTitle("season", r).title).toBe("Season Complete");
  });
  it("playoff variants", () => {
    const po = recap({ kind: "playoff" });
    expect(simRecapPageTitle("result", po, { roundLabel: "Semifinals" }).title).toBe("Semifinals");
    expect(simRecapPageTitle("result", recap({ kind: "playoff", your_game: { result: "bye", starters: [] } as never }), { roundLabel: "Semifinals" }).title).toBe("Playoff Bye");
    expect(simRecapPageTitle("result", recap({ your_game: { result: "bye", starters: [] } as never })).title).toBe("Bye Week");
    expect(simRecapPageTitle("result", recap({ your_game: { ...recap().your_game!, result: "win", your_pts: 130, opp_pts: 100 } })).subtitle).toBe("You won by 30.0 over Snap Crackle Pop");
  });
});

describe("team identity fit ladder", () => {
  it("never cuts a name: one line, then wrapped, then a smaller wrapped step", () => {
    expect(simTeamNameFit("Snap Crackle Pop").stage).toBe(0);
    expect(simTeamNameFit("Trade Deadline Titans", true)).toMatchObject({ stage: 1, wrap: true });
    expect(simTeamNameFit("The Extraordinarily Long Named Franchise Of Doom", false)).toMatchObject({ stage: 2, wrap: true, scale: 0.88 });
  });
  it("has a size table", () => {
    expect(SIM_TEAM_SIZES.hero).toBeGreaterThan(SIM_TEAM_SIZES.card);
    expect(SIM_TEAM_SIZES.row).toBeGreaterThan(SIM_TEAM_SIZES.chip);
  });
});
