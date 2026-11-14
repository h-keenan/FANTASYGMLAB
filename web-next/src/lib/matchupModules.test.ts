import { describe, expect, it } from "vitest";

import { collapsedVerdict } from "./moduleTemplates";
import { compactSummaryText, type CompactPart } from "./compactModule";
import { edgeChips, insightsParts, lineupParts, matchupHeroModel, movesParts, teamsValuesParts } from "./matchupModules";
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
