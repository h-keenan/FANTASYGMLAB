import { describe, expect, it } from "vitest";

import { PAGE_FACT_OWNERS, buildTeamStatusHeader, duplicatedFacts, factsOwnedBy, statusHeaderFacts } from "./statusHeader";
import { todayMatchupRing, todayTiles } from "./todayView";

// One owner module per fact (docs/ui-patterns.md). These tests fail when a page model states the same fact in two modules.
describe("duplicatedFacts", () => {
  it("flags a fact present in two modules, ignoring case and blanks", () => {
    expect(duplicatedFacts({ a: ["Record", ""], b: ["record", "holes"] })).toEqual([{ fact: "record", modules: ["a", "b"] }]);
    expect(duplicatedFacts({ a: ["record"], b: ["holes"] })).toEqual([]);
  });
});

describe("My Team: record, holes and injured have one owner", () => {
  const base = { teamValue: "10,000", valuePercentile: 100, leagueSize: 8, context: "Starters 6,000", openSlots: 1, flaggedStarters: 0, injuredStarters: 2, attention: [], hrefs: { lineup: "/l" } };
  const hero = buildTeamStatusHeader(base);

  it("the hero states only the facts it owns; the record belongs to Team Snapshot", () => {
    expect(statusHeaderFacts(hero).sort()).toEqual(["holes", "injured"]);
    expect(JSON.stringify(hero)).not.toMatch(/record/i);
  });
  it("no fact has two owner modules and the hero's facts are all hero-owned", () => {
    const owned: Record<string, string[]> = {};
    for (const owner of new Set(Object.values(PAGE_FACT_OWNERS.myTeam))) owned[owner] = factsOwnedBy("myTeam", owner);
    expect(duplicatedFacts(owned)).toEqual([]);
    expect(statusHeaderFacts(hero).every((f) => owned.hero.includes(f))).toBe(true);
  });
});

describe("Today: the Matchup hero owns week, opponent and score", () => {
  const standing = { record: "7-6", place: "1st of 8", playoffStatus: null, powerRank: null, playoffOdds: "60%", projectedRecord: null, tone: "neutral" as const };
  const ring = todayMatchupRing({ week: 10, opponentName: "Shiesty", opponentAvatar: null, myName: "GG", myAvatar: null, winPercent: 57, myProjected: 118.3, opponentProjected: 109.7, live: null, stateLabel: null });
  const tiles = todayTiles({ standing, teamRank: { value: "#3", of: 8 } });

  it("no tile restates the week, opponent, score or win chance", () => {
    const heroFacts = ["wk 10", "shiesty", ring.scoreLine ?? "", "57%"];
    const tileText = tiles.map((t) => `${t.label} ${t.value} ${t.sub}`.toLowerCase()).join(" | ");
    for (const fact of heroFacts) expect(tileText).not.toContain(fact.toLowerCase());
  });
  it("owner map keeps matchup facts out of the other Today modules", () => {
    const owned = Object.fromEntries(["matchup", "tiles", "trade"].map((o) => [o, factsOwnedBy("today", o)]));
    expect(duplicatedFacts(owned)).toEqual([]);
    expect(tiles.map((t) => t.key).every((k) => factsOwnedBy("today", "tiles").includes(k))).toBe(true);
  });
});
