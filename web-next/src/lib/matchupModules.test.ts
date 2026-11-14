import { describe, expect, it } from "vitest";

import { collapsedVerdict } from "./moduleTemplates";
import { compactSummaryText, type CompactPart } from "./compactModule";
import { edgeChips, insightsParts, lineupParts, matchupCardModel, matchupHeroModel, matchupSwingPlayers, matchupTickerParts, movesParts, simMatchupCardModel, teamsValuesParts } from "./matchupModules";
import { picksSummaryParts } from "./playersModules";

const base = {
  week: 10,
  myName: "Not Your Dad's Dih",
  opponentName: "Shiesty",
  myScore: 27.2,
  opponentScore: 0,
  myProjected: 118.3,
  opponentProjected: 109.7,
  winPercent: 57,
  kickedOff: true,
  live: true,
  final: false,
};

describe("matchupHeroModel", () => {
  it("leads with the win chance and names both teams, score and projections in the context", () => {
    const hero = matchupHeroModel(base);
    expect(hero.value).toBe("57%");
    expect(hero.label).toBe("Live · Win chance");
    expect(hero.context).toBe("vs Shiesty · 27.2 - 0.0 · Proj 118.3 - 109.7");
    expect(hero.tone).toBe("success");
  });
  it("falls back to the score, then the projections, when odds are missing", () => {
    expect(matchupHeroModel({ ...base, winPercent: null }).value).toBe("27.2 - 0.0");
    const pre = matchupHeroModel({ ...base, winPercent: null, kickedOff: false, live: false });
    expect(pre.value).toBe("118.3 - 109.7");
    expect(pre.context).toBe("vs Shiesty");
  });
  it("calls an underdog danger and a coin flip accent", () => {
    expect(matchupHeroModel({ ...base, winPercent: 30 }).tone).toBe("danger");
    expect(matchupHeroModel({ ...base, winPercent: 50 }).tone).toBe("accent");
  });
});

describe("collapsed summaries are never empty headers", () => {
  const edges = [
    { position: "RB", edge: 16.7 },
    { position: "QB", edge: 0.4 },
    { position: "TE", edge: -3.2 },
    { position: "WR", edge: -4.6 },
  ];
  const cases: Record<string, CompactPart[]> = {
    insights: insightsParts("You're on track to win.", "success", edges),
    teams: teamsValuesParts({ myValue: "45,719", opponentValue: "48,673", valueMargin: "-2,954", edge: "opponent", projectedMargin: 8.6 }),
    lineup: lineupParts({ view: "suggested", mineTotal: 118.3, opponentTotal: 109.7, slotCount: 9 }),
    lineupEmpty: lineupParts({ view: "actual", mineTotal: null, opponentTotal: null, slotCount: 0 }),
    moves: movesParts([{ startName: "Gibbs", gain: 4.2 }, { startName: "Chase", gain: 1 }]),
    movesNone: movesParts([]),
    movesWaiting: movesParts(null),
    picks: picksSummaryParts([{ label: "2027 1st", season: 2027, score: 900 }, { label: "2028 2nd", season: 2028, score: 300 }]),
  };
  for (const [name, parts] of Object.entries(cases)) {
    it(`${name} carries at least the minimum of real text`, () => {
      expect(collapsedVerdict(parts).ok).toBe(true);
    });
  }
  it("insights name the verdict, best and worst position", () => {
    expect(compactSummaryText(cases.insights)).toBe("You're on track to win · RB +16.7 · WR -4.6");
  });
  it("moves name the count and the biggest gain", () => {
    expect(compactSummaryText(cases.moves)).toBe("2 moves · Start Gibbs +4.2 pts");
  });
  it("picks summarise count, seasons and the top pick", () => {
    expect(compactSummaryText(cases.picks)).toBe("2 picks · 2027-2028 · Top 2027 1st");
  });
});

describe("edgeChips", () => {
  it("orders by the biggest swing and tones by sign", () => {
    const chips = edgeChips([{ position: "K", edge: -0.7 }, { position: "RB", edge: 16.7 }, { position: "QB", edge: 0 }]);
    expect(chips.map((c) => c.label)).toEqual(["RB +16.7", "K -0.7", "QB 0.0"]);
    expect(chips.map((c) => c.tone)).toEqual(["success", "danger", "muted"]);
  });
});

describe("matchup hero card and ticker", () => {
  const swing = (side: "mine" | "opponent", name: string, low: number | null, high: number | null, done = false) => ({ playerId: name, name, position: "WR", team: "CIN", low, high, done, side });
  it("picks the widest projection range still to play on each side", () => {
    const picks = matchupSwingPlayers([swing("mine", "Chase", 8, 26), swing("mine", "Tiny", 8, 9), swing("opponent", "Cook", 4, 12), swing("opponent", "Done", 0, 40, true)], "Mike");
    expect(picks.map((p) => p.name)).toEqual(["Chase", "Cook"]);
    expect(picks[0].label).toBe("±9 either way");
    expect(picks[1].label).toBe("±4 for Mike");
    expect(matchupSwingPlayers([swing("mine", "NoRange", null, null)], "Mike")).toEqual([]);
  });
  const base = { week: 7, live: true, final: false, myName: "You", opponentName: "Mike", myScore: 112.4, opponentScore: 98.1, myProjected: 131.2, opponentProjected: 124, winPercent: 71, kickedOff: true, playersLeft: 3, swing: [] };
  it("live: real points big, projection and players left under them", () => {
    const model = matchupCardModel(base);
    expect(model.kicker).toBe("WEEK 7 · LIVE");
    expect(model.win).toMatchObject({ pct: 71, label: "71% win", tone: "success" });
    expect(model.mine.score).toBe("112.4");
    expect(model.detail).toBe("Proj final 131.2 - 124.0 · 3 players left");
    expect(matchupTickerParts(model, 7).map((p) => p.text)).toEqual(["WK 7", "You 112.4 - 98.1 Mike", "71%"]);
  });
  it("before kickoff: projections are the scores and nothing is invented", () => {
    const model = matchupCardModel({ ...base, live: false, kickedOff: false, myScore: null, opponentScore: null, playersLeft: null, winPercent: null });
    expect(model.basis).toBe("projected");
    expect(model.mine.score).toBe("131.2");
    expect(model.win).toBeNull();
    expect(model.bar).toBeNull();
    expect(model.detail).toBeNull();
  });
  it("sim: floor and ceiling make the swing, an out player never swings, no rating leaks", () => {
    const p = (id: string, floor: number, ceiling: number, status = "healthy") => ({ id, headshot_id: `h${id}`, name: `P${id}`, pos: "RB", team: "DET", floor, ceiling, status });
    const model = simMatchupCardModel({ week: 4, playoff: false, opponentName: "Titans", youName: "You", youProjection: 120, oppProjection: 110, winProb: 0.62, rows: [{ you: p("1", 5, 25), opp: p("2", 0, 30, "out") }, { you: p("3", 9, 13), opp: p("4", 6, 18) }] });
    expect(model.kicker).toBe("WEEK 4");
    expect(model.swing.map((s) => s.name)).toEqual(["P1", "P4"]);
    expect(model.swing[0].playerId).toBe("h1");
    expect(JSON.stringify(model)).not.toMatch(/overall|value_rank/);
  });
});
