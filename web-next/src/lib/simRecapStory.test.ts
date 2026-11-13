import { describe, expect, it } from "vitest";

import type { SimGamePlayer, SimWeekRecap } from "./simGame";
import { STORY_ITEMS, simLeagueHighlights, simNextWeekModel, simPositionTotals, simRecapInjuryModel, simRecapPageKeys, simRecapResultModel, simTopStarters } from "./simRecapStory";

const p = (id: string, name: string, pos: string, projection = 10) => ({ id, name, pos, projection }) as unknown as SimGamePlayer;
const starter = (slot: string, player: SimGamePlayer | null, pts: number, flag: "bye" | "out" | null = null) => ({ slot, player, pts, flag }) as never;

function recap(over: Partial<SimWeekRecap> = {}): SimWeekRecap {
  return {
    week: 4,
    kind: "regular",
    round: null,
    your_game: {
      opponent_id: "7",
      opponent_name: "Rats",
      your_pts: 128.4,
      opp_pts: 109.7,
      result: "win",
      starters: [starter("QB", p("q", "Quinn", "QB"), 25), starter("RB", p("r", "Ross", "RB"), 20), starter("FLEX", p("w", "Wade", "RB"), 8), starter("WR", p("x", "Xan", "WR"), 0, "bye")],
      optimal_pts: 134.2,
      efficiency: 0.96,
    },
    scores: [
      { home: "1", away: "2", home_pts: 102, away_pts: 95, winner: "1" },
      { home: "3", away: "4", home_pts: 140.7, away_pts: 68.9, winner: "3" },
    ],
    injuries: [],
    season_complete: false,
    champion: null,
    next_week: 5,
    ...over,
  } as SimWeekRecap;
}
const facts = { youId: "9", names: { "1": "Goats", "2": "Brigade", "3": "Flex", "4": "Boom" }, lineupWarnings: 0, offers: 0 };

describe("simRecapPageKeys", () => {
  it("is Result, Matchup, Injuries, League, Next in that order and drops empty pages", () => {
    expect(simRecapPageKeys(recap(), facts)).toEqual(["result", "matchup", "injuries", "league", "next"]); // the bye starter flags the lineup page
    const clean = recap({ your_game: { ...recap().your_game!, starters: [starter("QB", p("q", "Quinn", "QB"), 25)] } });
    expect(simRecapPageKeys(clean, facts)).toEqual(["result", "matchup", "league", "next"]);
    expect(simRecapPageKeys(clean, { ...facts, lineupWarnings: 2 })).toContain("injuries");
    expect(simRecapPageKeys(recap({ your_game: null, scores: [], injuries: [] }), facts)).toEqual(["result", "next"]);
    expect(simRecapPageKeys(recap({ season_complete: true, next_week: null }), facts)).not.toContain("next");
  });
});

describe("page models", () => {
  it("result: margin, best and worst performers", () => {
    const m = simRecapResultModel(recap());
    expect(m).toMatchObject({ kind: "game", margin: "Won by 18.7", opponent: "Rats" });
    expect(m.best).toEqual({ name: "Quinn", pts: 25 });
    expect(m.worst).toEqual({ name: "Wade", pts: 8 }); // the bye starter is not a performance
    expect(simRecapResultModel(recap({ your_game: null })).kind).toBe("bye");
  });
  it("matchup: points by the player's own position, top starters capped", () => {
    const g = recap().your_game!;
    expect(simPositionTotals(g.starters).map((r) => [r.pos, r.pts, r.count])).toEqual([["QB", 25, 1], ["RB", 28, 2], ["WR", 0, 1]]);
    expect(simTopStarters(g.starters).map((s) => s.player!.name)).toEqual(["Quinn", "Ross", "Wade"]);
    expect(simTopStarters(g.starters, 2)).toHaveLength(2);
  });
  it("injuries: yours first, capped; zero starters named", () => {
    const hurt = (id: string, mine: boolean, weeks: number) => ({ player: p(id, id, "RB"), weeks, team_id: "x", is_yours: mine });
    const m = simRecapInjuryModel(recap({ injuries: [hurt("a", false, 9), hurt("b", true, 2), hurt("c", false, 1), hurt("d", false, 3), hurt("e", false, 4)] }));
    expect(m.yours).toBe(1);
    expect(m.items.map((i) => i.player.id)).toEqual(["b", "a", "e"]);
    expect(m.items.length).toBeLessThanOrEqual(STORY_ITEMS);
    expect(m.zeroStarters).toEqual([{ name: "Xan", flag: "bye" }]);
  });
  it("league: top score hero, closest game and blowout items, at most three", () => {
    const h = simLeagueHighlights(recap({ transactions: [{ type: "trade", text: "A traded B to C" } as never], waivers: [] }), facts.names);
    expect(h.hero).toEqual({ key: "top", label: "Top score", detail: "Flex 140.7", value: "140.7", who: "Flex" });
    expect(h.items.map((i) => i.key)).toEqual(["closest", "blowout", "trade"]);
    expect(h.items[0].detail).toBe("Goats beat Brigade by 7.0");
    expect(simLeagueHighlights(recap({ scores: [{ home: "1", away: "2", home_pts: null, away_pts: null, winner: null }] }), facts.names).hero).toBeNull();
  });
  it("next week: opponent edge and the notes that need attention", () => {
    const m = simNextWeekModel(recap(), { ...facts, lineupWarnings: 1, offers: 2, nextOpponent: "Titans", nextProjection: { yours: 121.4, theirs: 117.9 }, tradeDeadlineWeek: 10 });
    expect(m).toMatchObject({ week: 5, opponent: "Titans", edge: "You are favored by 3.5" });
    expect(m.notes).toEqual([{ label: "Lineup", text: "1 issue to fix" }, { label: "Offers", text: "2 waiting, they expire when you advance" }, { label: "Deadline", text: "Trade deadline in 5 weeks" }]);
    expect(simNextWeekModel(recap(), { ...facts, nextProjection: { yours: 100, theirs: 104 } }).edge).toBe("You are the underdog by 4.0");
  });
});
