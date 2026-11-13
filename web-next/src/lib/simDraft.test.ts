import { describe, expect, it } from "vitest";

import {
  simBoardEdge,
  simBoardProjection,
  simDraftAdpDelta,
  simDraftBestByPosition,
  simDraftBoardGrid,
  simDraftNeedPills,
  simDraftNextPickLabel,
  simDraftProgress,
  simDraftRecentPicks,
  simDraftMeta,
  simDraftRowChips,
  simListStats,
  simDraftTeamEmblem,
} from "./simDraft";
import type { SimDraftPick, SimGamePlayer } from "./simGame";

const p = (id: string, pos: SimGamePlayer["pos"], over: Partial<SimGamePlayer> = {}): SimGamePlayer =>
  ({ id, name: id, pos, team: "KC", age: 25, adp: 5, value: 1, projection: 1, floor: 0, ceiling: 2, status: "healthy", out_weeks: 0, bye_week: 9, ...over }) as SimGamePlayer;
const pk = (no: number, round: number, team: string): SimDraftPick => ({ pick_no: no, round, team_id: team, player: p(`p${no}`, "RB"), adp: null, value_over_adp: null, auto: false });

describe("simDraft helpers", () => {
  it("computes round/pick progress", () => {
    const pr = simDraftProgress({ pick_no: 16, total_picks: 168, status: "in_progress" }, 12);
    expect(pr).toMatchObject({ round: 2, pickInRound: 4, totalRounds: 14, made: 15 });
    expect(simDraftProgress({ pick_no: 169, total_picks: 168, status: "complete" }, 12).fraction).toBe(1);
  });
  it("orders recent picks newest first", () => {
    expect(simDraftRecentPicks([pk(1, 1, "a"), pk(3, 1, "c"), pk(2, 1, "b")], 2).map((x) => x.pick_no)).toEqual([3, 2]);
  });
  it("builds team emblems", () => {
    expect(simDraftTeamEmblem("Dynasty Dogs (you)")).toBe("DD");
    expect(simDraftTeamEmblem("Rivals")).toBe("RI");
    expect(simDraftTeamEmblem("")).toBe("?");
  });
  it("labels the countdown", () => {
    const base = { status: "in_progress" as const, on_the_clock: { team_id: "1", name: "x", is_you: false }, picks_until_you: 4, your_pick_numbers: [3, 20], pick_no: 16 };
    expect(simDraftNextPickLabel(base)).toEqual({ label: "4", detail: "picks until yours (#20)" });
    expect(simDraftNextPickLabel({ ...base, on_the_clock: { team_id: "1", name: "x", is_you: true } }).label).toBe("Now");
    expect(simDraftNextPickLabel({ ...base, status: "complete" }).label).toBe("Done");
  });
  it("picks best by position", () => {
    const out = simDraftBestByPosition([p("a", "WR"), p("b", "RB"), p("c", "WR")], ["QB", "RB", "WR"]);
    expect(out.map((x) => x.player?.id ?? null)).toEqual([null, "b", "a"]);
  });
  it("colors needs", () => {
    const slots = ["QB", "RB", "RB", "WR", "FLEX"] as never;
    const tones = Object.fromEntries(simDraftNeedPills([p("a", "RB")], slots).map((n) => [n.pos, n.tone]));
    expect(tones).toMatchObject({ QB: "danger", RB: "warning", WR: "danger", TE: "muted" });
  });
  it("flags steals and reaches against the clock", () => {
    expect(simDraftAdpDelta(10, 16)).toEqual({ delta: 6, label: "+6", tone: "success" });
    expect(simDraftAdpDelta(40, 16)).toEqual({ delta: -24, label: "-24", tone: "danger" });
    expect(simDraftAdpDelta(15, 16)).toBeNull();
    expect(simDraftAdpDelta(null, 16)).toBeNull();
  });
  it("shows a chip only for an out player", () => {
    expect(simDraftRowChips(p("a", "RB"))).toEqual([]);
    expect(simDraftRowChips(p("a", "RB", { status: "out", out_weeks: 4 }))).toEqual([{ key: "out", label: "Out 4w", tone: "danger" }]);
  });
  it("always shows the bye week; warns only when it is in the next 3 game weeks", () => {
    const byeOf = (over: Partial<SimGamePlayer>, week = 0) => simDraftMeta(p("a", "WR", over), week).find((x) => x.key === "bye");
    expect(byeOf({ bye_week: 9 })).toEqual({ key: "bye", text: "Bye 9", tone: undefined });
    expect(byeOf({ bye_week: 3 })?.tone).toBe("warning");
    expect(byeOf({ bye_week: 4 })?.tone).toBeUndefined();
    expect(byeOf({ bye_week: 7 }, 6)?.tone).toBe("warning");
    expect(byeOf({ bye_week: 5 }, 6)?.tone).toBeUndefined();
    expect(simDraftMeta(p("a", "WR", { bye_week: null }))).not.toContainEqual(expect.objectContaining({ key: "bye" }));
  });
  it("meta line: team, age (a tenth when sent), rookie", () => {
    expect(simDraftMeta(p("a", "WR", { age: 24 })).map((x) => x.text)).toEqual(["KC", "Age 24", "Bye 9"]);
    expect(simDraftMeta({ ...p("a", "WR", { age: 24 }), age_decimal: 24.34 }).map((x) => x.text)[1]).toBe("Age 24.3");
    expect(simDraftMeta(p("a", "WR", { age: 21, status: "out", out_weeks: 1 })).map((x) => x.text)).toEqual(["KC", "Age 21", "Bye 9", "Rookie"]);
  });
  it("list stats show the player's Overall as the OVR gauge, never a bare value", () => {
    const keys = (stats: ReturnType<typeof simListStats>) => stats.map((x) => x.key);
    const stats = simListStats({ ...p("a", "RB"), overall: 88, value: 70 });
    expect(keys(stats)).toEqual(["proj", "ovr", "adp"]);
    expect(stats.find((x) => x.key === "ovr")).toMatchObject({ label: "OVR", rating: 88 });
    expect(stats.some((x) => /^val/i.test(x.label))).toBe(false);
    // no overall (thin position pool or an older server): no number rather than a made-up one
    expect(keys(simListStats({ ...p("a", "RB"), overall: null }))).toEqual(["proj", "adp"]);
  });
  it("trade screens show Trade value (with its explainer) instead of Overall, never both", () => {
    const stats = simListStats({ ...p("a", "RB"), overall: 88, value: 70.4 }, { adp: false, tradeValue: true });
    expect(stats.map((x) => x.key)).toEqual(["proj", "tval"]);
    expect(stats[1]).toMatchObject({ label: "Trade value", value: "70", why: "trade_value" });
  });
  it("builds a rounds x teams grid keyed by team", () => {
    const grid = simDraftBoardGrid(
      {
        total_picks: 4,
        teams: [{ team_id: "a", name: "A", is_you: true }, { team_id: "b", name: "B", is_you: false }],
        order: [{ pick_no: 1, round: 1, team_id: "a" }, { pick_no: 2, round: 1, team_id: "b" }, { pick_no: 3, round: 2, team_id: "b" }, { pick_no: 4, round: 2, team_id: "a" }],
        picks: [pk(1, 1, "a"), pk(2, 1, "b")],
      },
      2,
    );
    expect(grid.teams.map((t) => t.team_id)).toEqual(["a", "b"]);
    expect(grid.rows[1].map((c) => c.pickNo)).toEqual([4, 3]);
    expect(grid.rows[0][0].pick?.pick_no).toBe(1);
    expect(grid.rows[1][0].pick).toBeNull();
  });
  it("board edge: market ADP vs model value rank, not the pick on the clock", () => {
    expect(simBoardEdge({ adp: 40, value_rank: 22 })).toEqual({ delta: 18, label: "+18", tone: "success" });
    expect(simBoardEdge({ adp: 10, value_rank: 25 })).toEqual({ delta: -15, label: "-15", tone: "danger" });
    expect(simBoardEdge({ adp: 20, value_rank: 22 })).toBeNull();
    expect(simBoardEdge({ adp: 30, value_rank: 28, adp_edge: 9.4 })?.delta).toBe(9);
    expect(simBoardEdge({ adp: 30 })).toBeNull();
  });
  it("shows an injured player's per-game projection instead of 0.0", () => {
    expect(simBoardProjection({ status: "out", projection: 0, ros_mean: 17.4 })).toEqual({ value: 17.4, discounted: true });
    expect(simBoardProjection({ status: "healthy", projection: 12.1, ros_mean: 12.1 })).toEqual({ value: 12.1, discounted: false });
    expect(simBoardProjection({ status: "out", projection: 0 })).toEqual({ value: 0, discounted: false });
  });
});
