import assert from 'node:assert/strict';
import { describe, it } from 'node:test';


import {
  STATUS_ATTENTION_LIMIT,
  STATUS_STAT_LIMIT,
  buildSimStatusHeader,
  buildTeamStatusHeader,
  buildTodayStatusHeader,
  lineupAttentionItems,
  rankPercentile,
  rosterAttentionItems,
  simHomeAttentionItems,
  splitTodayAttention,
  statusHeaderModel,
  statusRing,
  type StatusMoveInput,
  type StatusSimPlayerInput,
} from "./statusHeader.ts";

// Tiny jest-style matcher set so this file stays line-for-line comparable with web-next/src/lib/statusHeader.test.ts.
const subset = (actual: any, expected: any): void => {
  for (const key of Object.keys(expected)) {
    if (expected[key] && typeof expected[key] === 'object') subset(actual[key], expected[key]);
    else assert.equal(actual[key], expected[key]);
  }
};
const expect = (actual: any) => ({
  toBe: (e: unknown) => assert.equal(actual, e),
  toEqual: (e: unknown) => assert.deepEqual(actual, e),
  toBeNull: () => assert.equal(actual, null),
  toHaveLength: (n: number) => assert.equal(actual.length, n),
  toBeLessThanOrEqual: (n: number) => assert.ok(actual <= n),
  toMatchObject: (e: object) => subset(actual, e),
  not: { toMatch: (re: RegExp) => assert.ok(!re.test(actual)) },
});

const player = (name: string, id: string | null = "1") => ({ player_id: id, name, position: "RB", team: "HOU", tier: null, injury_label: "" });
const move = (over: string, start: string, gain: number | null, reason: StatusMoveInput["over_reason"] = "ruled_out"): StatusMoveInput => ({ start: player(start, "9"), over: player(over, "8"), over_reason: reason, gain, locked: false });

describe("status ring", () => {
  it("clamps, rounds and picks a tone", () => {
    expect(statusRing(71.4, "71%", "Win chance 71%").pct).toBe(71);
    expect(statusRing(150, "x", "x").pct).toBe(100);
    expect(statusRing(null, "x", "x").pct).toBeNull();
    expect(statusRing(60, "a", "a").tone).toBe("success");
    expect(statusRing(40, "a", "a").tone).toBe("danger");
    expect(statusRing(50, "a", "a").tone).toBe("accent");
  });
  it("turns a rank into a league percentile", () => {
    expect(rankPercentile(1, 12)).toBe(100);
    expect(rankPercentile(12, 12)).toBe(0);
    expect(rankPercentile(3, 1)).toBeNull();
    expect(rankPercentile(null, 12)).toBeNull();
  });
});

describe("statusHeaderModel", () => {
  it("caps stats and rows and drops empty values instead of zero-filling", () => {
    const row = (n: number) => ({ key: `k${n}`, playerId: null, name: `P${n}`, position: "WR", team: null, meta: "m" });
    const model = statusHeaderModel({
      kicker: "TODAY", headline: "h", context: null, ring: null, primary: null,
      stats: [1, 2, 3, 4].map((n) => ({ key: `s${n}`, label: "L", value: n === 2 ? "" : String(n) })),
      attention: [1, 2, 3, 4, 5].map(row),
    });
    expect(model.stats.map((s) => s.key)).toEqual(["s1", "s3", "s4"]);
    expect(model.stats.length).toBeLessThanOrEqual(STATUS_STAT_LIMIT);
    expect(model.attention).toHaveLength(STATUS_ATTENTION_LIMIT);
  });
});

describe("FantasyDesk adapters", () => {
  it("lineup holes become player rows with the swap and its gain; empty slots and locked moves do not", () => {
    const rows = lineupAttentionItems([move("Hurt Back", "Backup", 6.2), move("Bye WR", "Sub", 0, "bye_week"), move("X", "Y", 3, "empty_slot"), { ...move("Locked", "Z", 2), locked: true }]);
    expect(rows.map((r) => r.name)).toEqual(["Hurt Back", "Bye WR"]);
    expect(rows[0]).toMatchObject({ playerId: "8", stat: { value: "+6.2", label: "GAIN" } });
    expect(rows[0].meta).toBe("Ruled out this week · Start Backup instead");
    expect(rows[1].stat).toBeNull();
  });
  it("roster rows put out starters before injury tags", () => {
    const base = { player_id: "a", name: "A", position: "WR", team: "CIN", tier: null, injury_label: "", injury_status: null, ruled_out: false, slot: "WR1" };
    const rows = rosterAttentionItems([{ ...base, player_id: "q", name: "Questionable", injury_label: "Q" }, { ...base, player_id: "o", name: "Out", ruled_out: true, injury_label: "Out" }, { ...base, player_id: "h", name: "Healthy" }]);
    expect(rows.map((r) => r.name)).toEqual(["Out", "Questionable"]);
  });
  it("splits Needs attention: absorbed entries leave the card, the rest stay", () => {
    const item = { headline: "Gibbs hurt", reason: "r", route_player_id: "5", route_player_name: "Gibbs", route_player_position: "RB", route_player_team: "DET", route_player_tier: "", route_player_score: null, route_player_injury_status: "Out" };
    const entries = [
      { source: "lineup", id: 1 },
      { source: "deadline", id: 2 },
      { source: "item", id: 3, item },
      { source: "item", id: 4 },
    ];
    const { rows, remaining } = splitTodayAttention(entries, [move("Hurt", "B", 2)], () => "/x");
    expect(rows.map((r) => r.name)).toEqual(["Hurt", "Gibbs"]);
    expect(remaining.map((e) => e.id)).toEqual([2, 4]);
    // No moves: the lineup entry stays in the card.
    expect(splitTodayAttention(entries, [], () => "/x").remaining.map((e) => e.id)).toEqual([1, 2, 4]);
  });
  const hrefs = { matchup: "/m", rankings: "/r", trades: "/t" };
  it("Today: ring is the win chance, a lineup hole is the headline and the one action", () => {
    const model = buildTodayStatusHeader({
      matchup: { week: 9, opponentName: "Rival", winPercent: 63, live: null },
      hero: { label: "Your win chance", value: "63%", context: "Week 9 vs Rival" },
      lineup: { tone: "risk", headline: "1 starter can't play" },
      standing: { place: "3rd of 12", record: "3-5", playoffOdds: "41%", tone: "neutral" },
      attention: lineupAttentionItems([move("Hurt", "B", 2)]),
      tradeCount: 2,
      hrefs,
    })!;
    expect(model.ring).toMatchObject({ pct: 63, center: "63%" });
    expect(model.headline).toBe("1 starter can't play");
    expect(model.context).toBe("Week 9 vs Rival");
    expect(model.stats.map((s) => s.key)).toEqual(["standing", "odds", "trades"]);
    expect(model.primary).toEqual({ label: "Fix lineup", href: "/m" });
    expect(model.kicker).toBe("TODAY · WEEK 9");
  });
  it("Today: nothing to say means no header", () => {
    expect(buildTodayStatusHeader({ matchup: null, hero: null, lineup: null, standing: null, attention: [], tradeCount: 0, hrefs })).toBeNull();
  });
  it("Team: holes are the headline; a clean roster leads with Team Value and has no action", () => {
    const base = { teamValue: "8,000", valuePercentile: 62, leagueSize: 12, context: "62nd percentile", record: "3-5", openSlots: 0, flaggedStarters: 0, injuredStarters: 0, attention: [], hrefs: { lineup: "/l" } };
    const clean = buildTeamStatusHeader(base);
    expect(clean.headline).toBe("Team Value 8,000");
    expect(clean.primary).toBeNull();
    const holes = buildTeamStatusHeader({ ...base, openSlots: 1, flaggedStarters: 1 });
    expect(holes.headline).toBe("2 holes in your lineup");
    expect(holes.context).toBe("Team Value 8,000 · 62nd percentile");
    expect(holes.primary).toEqual({ label: "Fix lineup", href: "/l" });
  });
});

describe("Fantasy Sim adapters", () => {
  const sp = (id: string, name: string): StatusSimPlayerInput => ({ id, headshot_id: `h${id}`, name, pos: "RB", team: "DET", adp: 5.1, projection: 11.44 });
  it("orders out starters, uncovered byes, then the best waiver target, and never carries a rating", () => {
    const rows = simHomeAttentionItems({
      injuries: [{ player: sp("1", "Hurt"), starting: true, out_weeks: 3, note: "n" }, { player: sp("2", "BenchHurt"), starting: false, out_weeks: 1, note: "" }],
      bye_alerts: [{ player: sp("3", "Bye"), covered: false, week: 7, message: "m" }, { player: sp("4", "Covered"), covered: true, week: 8, message: "" }],
      waiver_suggestions: [{ player: sp("5", "Target"), gain_now: 4.14, gain_ros: 2, for_slot: "RB2" }],
    });
    expect(rows.map((r) => r.name)).toEqual(["Hurt", "Bye", "Target"]);
    expect(rows[0].playerId).toBe("h1");
    expect(rows[2].stat).toEqual({ value: "+4.1", label: "GAIN", tone: "success" });
    expect(JSON.stringify(rows)).not.toMatch(/value_rank|overall|"ovr"/i);
  });
  it("Home: ring is the win chance, a bye week has no ring, the first open step is the action", () => {
    const base = { week: 7, seasonLabel: "Season 3", record: "5-1", rank: 2, teams: 12, inPlayoffs: true, opponentName: "Titans", winProb: 0.623, bye: false, injuredCount: 1, offers: 0, waiverTargets: 2, attention: [], next: { label: "Set your lineup", actionKey: "team" } };
    const model = buildSimStatusHeader(base);
    expect(model.kicker).toBe("WEEK 7 · SEASON 3");
    expect(model.headline).toBe("You are 5-1");
    expect(model.context).toBe("Next: vs Titans, 62% to win");
    expect(model.ring?.pct).toBe(62);
    expect(model.stats.map((s) => s.key)).toEqual(["standing", "injuries", "waivers"]);
    expect(model.primary).toEqual({ label: "Set your lineup", actionKey: "team" });
    const bye = buildSimStatusHeader({ ...base, bye: true, next: null });
    expect(bye.ring).toBeNull();
    expect(bye.primary).toBeNull();
  });
});
