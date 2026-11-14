import { describe, expect, it } from "vitest";

import type { SimGamePlayer, SimWeekRecap } from "./simGame";
import { STORY_ITEMS, simLeagueHighlights, simNextWeekModel, simPositionTotals, simRecapInjuryModel, simRecapOutcome, simRecapPageKeys, simRecapProj, simRecapResultModel, simRecapSeasonModel, simTopStarters } from "./simRecapStory";

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
    expect(m.best).toMatchObject({ name: "Quinn", pts: 25 });
    expect(m.worst).toMatchObject({ name: "Wade", pts: 8 }); // the bye starter is not a performance
    expect(simRecapResultModel(recap({ your_game: null })).kind).toBe("bye");
  });
  it("a playoff bye (server sends a game with result 'bye') is a bye: no NaN margin, no made-up performers, no matchup page", () => {
    const r = recap({ your_game: { ...recap().your_game!, result: "bye" as never } });
    expect(simRecapResultModel(r)).toMatchObject({ kind: "bye", margin: "Bye week", best: null, worst: null });
    expect(simRecapPageKeys(r, { names: {}, lineupWarnings: 0, offers: 0 })).not.toContain("matchup");
  });
  it("matchup: points by the player's own position, top starters capped", () => {
    const g = recap().your_game!;
    expect(simPositionTotals(g.starters).map((r) => [r.pos, r.pts, r.count])).toEqual([["QB", 25, 1], ["RB", 28, 2], ["WR", 0, 1]]);
    expect(simTopStarters(g.starters).map((s) => s.player!.name)).toEqual(["Quinn", "Ross", "Wade"]);
    expect(simTopStarters(g.starters, 2)).toHaveLength(2);
  });
  it("matchup: the row's PROJ is the projection the server stamped for that week, never a guess", () => {
    expect(simRecapProj({ proj: 14.23 })).toBe(14.23);
    expect(simRecapProj({ proj: 0 })).toBe(0);
    expect(simRecapProj({})).toBeNull(); // a recap saved before the server sent it
    expect(simRecapProj({ proj: null })).toBeNull();
    expect(simRecapProj({ proj: Number.NaN })).toBeNull();
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

describe("simRecapOutcome (result variants)", () => {
  const playoff = (over: Partial<SimWeekRecap>) => recap({ kind: "playoff", round: 1, ...over });
  const game = (result: string) => ({ ...recap().your_game!, result }) as never;
  it("regular season: win, loss, tie, bye, no trophy and no confetti", () => {
    expect(simRecapOutcome(recap(), "9")).toMatchObject({ variant: "win", tone: "success", trophy: false, celebrate: false });
    expect(simRecapOutcome(recap({ your_game: game("loss") }), "9")).toMatchObject({ variant: "loss", tone: "danger" });
    expect(simRecapOutcome(recap({ your_game: game("tie") }), "9").variant).toBe("tie");
    expect(simRecapOutcome(recap({ your_game: null }), "9")).toMatchObject({ variant: "bye", trophy: false });
  });
  it("playoffs: advance, eliminated and bye show the trophy but never confetti", () => {
    expect(simRecapOutcome(playoff({}), "9")).toMatchObject({ variant: "advance", trophy: true, celebrate: false });
    expect(simRecapOutcome(playoff({ your_game: game("loss") }), "9")).toMatchObject({ variant: "eliminated", tone: "danger", trophy: true, celebrate: false });
    expect(simRecapOutcome(playoff({ your_game: null }), "9")).toMatchObject({ variant: "playoff_bye", trophy: true });
  });
  it("the championship: champion celebrates once, the finalist who lost is runner-up, nobody else is crowned", () => {
    const final = { season_complete: true, next_week: null, champion: "9" };
    expect(simRecapOutcome(playoff(final), "9")).toMatchObject({ variant: "champion", headline: "Champions", celebrate: true, trophy: true });
    expect(simRecapOutcome(playoff({ ...final, champion: "7", your_game: game("loss") }), "9")).toMatchObject({ variant: "runner_up", celebrate: false });
    expect(simRecapOutcome(playoff({ ...final, champion: "7", your_game: game("loss") }), "8").variant).toBe("runner_up");
    // a regular-season finale that completes the season is not a championship
    expect(simRecapOutcome(recap({ ...final, champion: "9" }), "9").celebrate).toBe(false);
  });
});

describe("season page", () => {
  const rows = [
    { rank: 1, team_id: "9", name: "You", is_you: true, wins: 11, losses: 3, ties: 0, pf: 1800.4, pa: 1500 },
    { rank: 2, team_id: "7", name: "Rats", is_you: false, wins: 10, losses: 4, ties: 0, pf: 1900.2, pa: 1400 },
    { rank: 3, team_id: "1", name: "Goats", is_you: false, wins: 7, losses: 7, ties: 0, pf: 1500, pa: 1500 },
  ];
  it("a season-complete recap adds the season page, last", () => {
    expect(simRecapPageKeys(recap({ season_complete: true, next_week: null }), facts).at(-1)).toBe("season");
    expect(simRecapPageKeys(recap(), facts)).not.toContain("season");
  });
  it("champion, finish, record and the points award, capped at the story limit", () => {
    const r = recap({ kind: "playoff", season_complete: true, champion: "7", next_week: null, standings: rows as never, your_game: { ...recap().your_game!, result: "loss" } });
    const m = simRecapSeasonModel(r, { ...facts, youId: "9", names: { "9": "You", "7": "Rats" } });
    expect(m).toMatchObject({ championName: "Rats", youChampion: false, finish: "Runner-up", record: "11-3" });
    expect(m.items.map((i) => i.key)).toEqual(["champion", "record", "top"]);
    expect(m.items.length).toBeLessThanOrEqual(STORY_ITEMS);
    const won = simRecapSeasonModel(recap({ kind: "playoff", season_complete: true, champion: "9", standings: rows as never }), { ...facts, youId: "9" });
    expect(won).toMatchObject({ youChampion: true, finish: "Champions" });
  });
  it("an ordinary finish reads '3rd of 3'", () => {
    const r = recap({ season_complete: true, champion: "7", standings: rows.map((x) => ({ ...x, is_you: x.team_id === "1" })) as never });
    expect(simRecapSeasonModel(r, { ...facts, youId: "1" }).finish).toBe("3rd of 3");
  });
});

describe("injuries: one marker per player", () => {
  it("the trailing detail is the duration only, never a second 'Out'", () => {
    const m = simRecapInjuryModel(recap({ injuries: [{ player: p("a", "Alf", "WR"), weeks: 4, team_id: "9", is_yours: true }, { player: p("b", "Bo", "RB"), weeks: 1, team_id: "2", is_yours: false }] as never }));
    expect(m.items.map((i) => i.detail)).toEqual(["4 weeks · yours", "1 week"]);
    expect(m.items.every((i) => !/out/i.test(i.detail))).toBe(true);
  });
});
