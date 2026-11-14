import { describe, expect, it } from "vitest";

import { reviewSectionParts, type ReviewSection } from "./simReview";
import { simAgePhase, simHeroTiles, simOutlookTiles, simProfileRead } from "./simPlayerSheet";
import { simHubAgo, simHubRow } from "./simHub";
import { compactSummaryText } from "./compactModule";
import { simBenchParts, simLineupParts, simMenuHero, simRulesParts, simStandingHero } from "./simSummaries";
import type { SimGameLite } from "./simGame";

const MIN = 12; // collapsed-module rule: at least 12 characters of real data

describe("review sections never collapse to an empty header", () => {
  const sections: ReviewSection[] = [
    { id: "grade", kind: "stats", glyph: "trophy", title: "How your grade was built", items: [{ label: "Record", value: "88", tone: "success" }, { label: "Points", value: "95", tone: "success" }] },
    { id: "path", kind: "path", glyph: "trophy", title: "Champion path", steps: [{ label: "R1", result: "bye" }, { label: "R2", result: "win" }, { label: "R3", result: "win" }], caption: "Zach (you), the #1 seed" },
    { id: "journey", kind: "journey", glyph: "rank", title: "Standings journey", teams: 12, points: [{ label: "W1", rank: 6 }, { label: "W2", rank: 3 }, { label: "W3", rank: 4 }] },
    { id: "games", kind: "games", glyph: "game", title: "Closest games", rows: [{ label: "You vs Rats", score: "101-100", tone: "success" }] },
    { id: "leaders", kind: "leaders", glyph: "leader", title: "Leaders", groups: [{ title: "WR", pos: "WR", rows: [{ player: { id: "1", name: "Chase Moore", pos: "WR" }, value: "200 pts" }] }] },
    { id: "cards", kind: "cards", glyph: "trade", title: "Trades", cards: [{ id: "c", glyph: "trade", tone: "success", label: "Best trade", headline: "Got Jaxon Moore", players: [], delta: { text: "+3.2 pts", tone: "success" } }] },
  ];
  it.each(sections.map((s) => [s.id, s] as const))("%s has a real summary", (_id, section) => {
    expect(compactSummaryText(reviewSectionParts(section) as never).length).toBeGreaterThanOrEqual(MIN);
  });
  it("journey says where the season went", () => {
    const text = compactSummaryText(reviewSectionParts(sections[2]) as never);
    expect(text).toContain("#6 → #4");
    expect(text).toContain("Peak #3");
    expect(text).toContain("Low #6");
  });
  it("path counts wins and notes the bye", () => {
    expect(compactSummaryText(reviewSectionParts(sections[1]) as never)).toContain("2-0 after a bye");
  });
});

describe("sim player sheet presentation", () => {
  const p = { projection: 20, next_projection: 21, projection_note: null, status: "healthy" as const, out_weeks: 0, floor: 10, ceiling: 31, adp: 12, adp_edge: 4 };
  it("hero tiles replace Value and Usage with this week and ADP, never a value", () => {
    const tiles = simHeroTiles(p);
    expect(tiles.map((t) => t.label)).toEqual(["This week", "ADP"]);
    expect(tiles.some((t) => /value/i.test(`${t.label} ${t.note}`))).toBe(false);
    expect(tiles[0].value).toBe("20.0");
    expect(simHeroTiles({ ...p, status: "out", out_weeks: 3, projection: 0 })[0]).toMatchObject({ value: "Out", note: "3 weeks" });
    expect(simHeroTiles({ ...p, projection_note: "bye", projection: 0 })[0].value).toBe("Bye");
  });
  it("outlook tiles describe the rest of the season", () => {
    const t = simOutlookTiles({ mean: 12, floor: 5, ceiling: 25, weeks_left: 10, playable_weeks: 9, bye_week: 7, out_weeks: [] });
    expect(t.map((x) => x.label)).toEqual(["Per game", "Range", "Games left", "Availability"]);
    expect(t[2].value).toBe("9");
    expect(t[3].note).toContain("Bye week 7");
    expect(simOutlookTiles(null)).toEqual([]);
  });
  it("age phase follows the position window", () => {
    expect(simAgePhase("RB", 22)?.phase).toBe("rising");
    expect(simAgePhase("RB", 26)?.phase).toBe("prime");
    expect(simAgePhase("RB", 29)?.phase).toBe("declining");
    expect(simAgePhase("QB", 36)?.phase).toBe("declining");
    expect(simAgePhase("WR", 34)?.phase).toBe("late");
    expect(simAgePhase("WR", null)).toBeNull();
  });
  it("a veteran gets a profile read built only from game fields, no value", () => {
    const read = simProfileRead({ pos: "WR", age: 27, overall: 88, adp: 20, adp_edge: 6, projection: 15, ros_mean: 15, floor: 6, ceiling: 31, games: 3, ppg: 14.2, season_points: 42.6, last_week: 12, team: "BUF" });
    expect(read.phase?.label).toBe("Prime");
    expect(read.tiles.map((t) => t.label)).toEqual(["Age", "Overall", "Range", "ADP"]);
    expect(read.lines.join(" ")).toMatch(/sim has him/);
    expect([...read.tiles.flatMap((t) => [t.label, t.note]), ...read.lines, ...read.chips.map((c) => c.label)].join(" ")).not.toMatch(/value/i);
  });
});

describe("hub rows", () => {
  const game = (over: Partial<SimGameLite> = {}): SimGameLite => ({
    id: "g", seed: 1, engine_version: "x", settings: { regular_weeks: 14, playoff_weeks: 3, teams: 12, scoring: "ppr" }, status: "in_season", current_week: 4,
    difficulty: "normal", grade_letter: null, event_count: 0, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-12T00:00:00Z", ...over,
  });
  const now = Date.parse("2026-11-14T12:00:00Z");
  it("in season: week progress, chip, setup and last played", () => {
    const row = simHubRow(game(), now);
    expect(row).toMatchObject({ title: "Week 4 of 14", progress: { done: 3, total: 17 }, meta: "12 teams · PPR · Normal", played: "Played 2d ago", open: true });
    expect(row.chip.label).toBe("In season");
  });
  it("finished: full bar and the grade as the chip, no Continue", () => {
    const row = simHubRow(game({ status: "complete", grade_letter: "B+" }), now);
    expect(row.progress).toEqual({ done: 17, total: 17 });
    expect(row.chip.label).toBe("B+");
    expect(row.open).toBe(false);
  });
  it("drafting has no progress bar", () => {
    expect(simHubRow(game({ status: "drafting" }), now).progress).toBeNull();
  });
  it("ago copy", () => {
    expect(simHubAgo("2026-11-14T01:00:00Z", now)).toBe("today");
    expect(simHubAgo("2026-11-13T01:00:00Z", now)).toBe("yesterday");
    expect(simHubAgo("2026-10-20T00:00:00Z", now)).toBe("3w ago");
    expect(simHubAgo("nope", now)).toBeNull();
  });
});

describe("team tab, standings and menu summaries", () => {
  it("lineup and bench summaries carry counts and problems", () => {
    const slots = [{ slot: "QB", player: { status: "healthy" } }, { slot: "RB", player: { status: "out" } }, { slot: "WR", player: { status: "bye" } }, { slot: "TE", player: null }];
    const text = compactSummaryText(simLineupParts({ slots, projected_total: 121.44, warnings: [{}] }));
    expect(text).toContain("4 starters");
    expect(text).toContain("proj 121.4");
    expect(text).toContain("1 issue");
    expect(text).toContain("1 out");
    expect(text).toContain("1 on bye");
    expect(text).toContain("1 empty");
    const bench = compactSummaryText(simBenchParts([{ pos: "WR", status: "bye" }, { pos: "WR" }, { pos: "RB" }], 16, 16));
    expect(bench).toContain("3 bench");
    expect(bench).toContain("16/16 spots");
    expect(bench).toContain("WR2 RB1");
    expect(simBenchParts([])[0].text).toBe("Empty bench");
  });
  it("standing hero: in the playoff spots vs on the outside", () => {
    const rows = Array.from({ length: 8 }, (_, i) => ({ rank: i + 1, wins: 7 - i, losses: i, ties: 0, pf: 800 - i * 10, is_you: i === 2 }));
    const inn = simStandingHero(rows, 6)!;
    expect(inn.value).toBe("#3");
    expect(inn.context).toContain("5-2");
    expect(inn.context).toContain("3rd in points");
    expect(inn.tone).toBe("success");
    const out = simStandingHero(rows.map((r, i) => ({ ...r, is_you: i === 7 })), 6)!;
    expect(out.tone).toBe("danger");
    expect(out.context).toMatch(/games? back of the 6th seed/);
    expect(simStandingHero(rows.map((r) => ({ ...r, is_you: false })), 6)).toBeNull();
  });
  it("menu hero and rules", () => {
    const hero = simMenuHero({ status: "in_season", week: 4, you: { wins: 2, losses: 1, ties: 0, rank: 4 }, settings: { teams: 12, regular_weeks: 14 } }, "Normal", "PPR");
    expect(hero.value).toBe("Week 4 of 14");
    expect(hero.context).toBe("2-1 · #4 of 12 · PPR · Normal");
    expect(compactSummaryText(simRulesParts({ regular_weeks: 14, playoff_teams: 6, trade_deadline_week: 10, roster_limit: 16 }))).toBe("14 weeks · 6 make playoffs · deadline wk 10 · roster 16");
  });
});
