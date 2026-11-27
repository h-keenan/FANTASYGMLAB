import { describe, expect, it } from "vitest";

import {
  STATUS_ATTENTION_LIMIT,
  STATUS_STAT_LIMIT,
  buildSimStatusHeader,
  buildTeamStatusHeader,
  buildTodayStatusHeader,
  ordinalRank,
  teamValueRingLabel,
  lineupAttentionItems,
  rankPercentile,
  rosterAttentionItems,
  simHomeAttentionItems,
  splitTodayAttention,
  statusHeaderModel,
  statusRing,
  type StatusMoveInput,
  type StatusSimPlayerInput,
} from "./statusHeader";
import { isActionableLineupIssue, isLineupLocked, leftGame } from "./lineupLock";

const player = (name: string, id: string | null = "1") => ({ player_id: id, name, position: "RB", team: "HOU", tier: null, injury_label: "" });
const move = (over: string, start: string, gain: number | null, reason: StatusMoveInput["over_reason"] = "ruled_out"): StatusMoveInput => ({ start: player(start, "9"), over: player(over, "8"), over_reason: reason, gain, locked: false });

describe("status ring", () => {
  it("clamps, rounds and picks a tone", () => {
    expect(statusRing(71.4, "71%", "Win chance 71%").pct).toBe(71);
    expect(statusRing(150, "x", "x").pct).toBe(100);
    expect(statusRing(null, "x", "x").pct).toBeNull();
    expect(statusRing(60, "a", "a").tone).toBe("success");
    expect(statusRing(10, "a", "a").tone).toBe("danger");
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
    expect(model.kicker).toBe("THIS WEEK");
  });
  it("Today: nothing to say means no header", () => {
    expect(buildTodayStatusHeader({ matchup: null, hero: null, lineup: null, standing: null, attention: [], tradeCount: 0, hrefs })).toBeNull();
  });
  it("Team: holes are the headline; a clean roster leads with Team Value and has no action", () => {
    const base = { teamValue: "8,000", valuePercentile: 62, leagueSize: 12, context: "62nd percentile", openSlots: 0, flaggedStarters: 0, injuredStarters: 0, attention: [], hrefs: { lineup: "/l" } };
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
    expect(model.context).toBe("Next: vs Titans");
    expect(model.ring?.pct).toBe(62);
    expect(model.stats.map((s) => s.key)).toEqual(["standing", "injuries", "waivers"]);
    expect(model.primary).toEqual({ label: "Set your lineup", actionKey: "team" });
    const bye = buildSimStatusHeader({ ...base, bye: true, next: null });
    expect(bye.ring).toBeNull();
    expect(bye.primary).toBeNull();
  });
});

describe("lock-aware lineup issues (one rule: lib/lineupLock.ts)", () => {
  const base = { player_id: "a", name: "A", position: "TE", team: "LV", tier: null, injury_label: "", injury_status: null, ruled_out: false, slot: "FLEX" };
  const out = { ...base, player_id: "l", name: "Loveland", ruled_out: true, injury_label: "Out" };

  it("a starter hurt mid-game is not an attention row, a hole or a Fix lineup", () => {
    const hurt = { ...out, game_locked: true, game_started: true };
    expect(rosterAttentionItems([hurt])).toEqual([]);
    expect(isActionableLineupIssue(hurt)).toBe(false);
    expect(leftGame(hurt)).toBe(true);
    const model = buildTeamStatusHeader({ teamValue: "8,000", valuePercentile: 22, valueRank: 8, leagueSize: 10, context: "8th of 10 teams", openSlots: 0, flaggedStarters: [hurt].filter((p) => isActionableLineupIssue(p)).length, injuredStarters: 1, leftGameNames: ["Loveland"], attention: [], hrefs: { lineup: "/l" } });
    expect(model.primary).toBeNull();
    expect(model.headline).toBe("Team Value 8,000");
    expect(model.context).toBe("8th of 10 teams · Loveland left game (injury)");
    expect(model.stats.find((st) => st.key === "holes")?.value).toBe("0");
    expect(JSON.stringify(model)).not.toMatch(/Fix lineup|in your lineup/);
  });
  it("Out before kickoff is flagged", () => {
    const pre = { ...out, game_started: false, game_locked: false };
    expect(rosterAttentionItems([pre]).map((r) => r.name)).toEqual(["Loveland"]);
    expect(isActionableLineupIssue(pre)).toBe(true);
    expect(leftGame(pre)).toBe(false);
  });
  it("a finished game is locked and not flagged", () => {
    const fin = { ...out, game_started: true };
    expect(rosterAttentionItems([fin])).toEqual([]);
    expect(isActionableLineupIssue(fin)).toBe(false);
  });
  it("a missing kickoff time never invents a lock", () => {
    const unknown = { ...out, game_started: null };
    expect(isLineupLocked(unknown)).toBe(false);
    expect(isActionableLineupIssue(unknown)).toBe(true);
  });
  it("a bye starter is flagged even though he has no game", () => {
    const bye = { ...base, name: "Bye", on_bye: true, start_ineligible_reason: "Bye", game_started: null };
    expect(isActionableLineupIssue(bye)).toBe(true);
  });
  it("mixed lineup: only the unstarted players are flagged", () => {
    const rows = rosterAttentionItems([
      { ...out, player_id: "1", name: "Locked", game_started: true },
      { ...out, player_id: "2", name: "Open", game_started: false },
      { ...base, player_id: "3", name: "Q", injury_label: "Q", game_started: true },
    ]);
    expect(rows.map((r) => r.name)).toEqual(["Open"]);
  });
  it("the server verdict wins over the raw fields", () => {
    expect(isActionableLineupIssue({ ...out, lineup_issue: false })).toBe(false);
    expect(leftGame({ left_game: true })).toBe(true);
  });
});

describe("team value label", () => {
  it("is a rank of N teams, never 'percentile 22 of 10 teams'", () => {
    expect(ordinalRank(8)).toBe("8th");
    expect(ordinalRank(11)).toBe("11th");
    expect(ordinalRank(22)).toBe("22nd");
    expect(teamValueRingLabel(22.2, 8, 10)).toBe("Team value rank 8th of 10 teams");
    expect(teamValueRingLabel(22.2, null, 10)).toBe("Team value ahead of 22% of the league");
    const ring = buildTeamStatusHeader({ teamValue: "1", valuePercentile: 22.2, valueRank: 8, leagueSize: 10, context: null, openSlots: 0, flaggedStarters: 0, injuredStarters: 0, attention: [], hrefs: { lineup: "/l" } }).ring;
    expect(ring?.label).toBe("Team value rank 8th of 10 teams");
    expect(ring?.center).toBe("#8");
    expect(ring?.label).not.toMatch(/percentile/);
  });
});
