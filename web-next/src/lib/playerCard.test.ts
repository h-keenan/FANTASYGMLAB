import { describe, expect, it } from "vitest";

import {
  estimatedQuarter,
  headlinePoints,
  playerCardAriaLabel,
  playerCardFromStarter,
  playerGameLine,
  playerGameStatusLine,
  liveStatLine,
  playerStatusChips,
  trendVsProjection,
  type PlayerCardSource,
} from "./playerCard";

const base: PlayerCardSource = {
  player_id: "1",
  name: "Cam Skattebo",
  position: "RB",
  team: "NYG",
  projection: { status: "ok", point_estimate: 14, opponent: "DAL" },
};

const live: PlayerCardSource = {
  ...base,
  game_status: "in_progress",
  game_started: true,
  actual_points: 11.2,
  projected_final: 17.4,
  game_progress: 0.55,
  game_opponent: "DAL",
  game_is_home: false,
};

describe("playerCard model", () => {
  it("builds a live model with projected final and quarter estimate", () => {
    const model = playerCardFromStarter(live);
    expect(model.points).toBe(11.2);
    expect(model.expectedFinal).toBe(17.4);
    expect(headlinePoints(model)).toEqual({ value: 11.2, kind: "pts" });
    expect(playerGameLine(model)).toBe("@ DAL · ~Q3");
    expect(playerStatusChips(model).map((chip) => chip.kind)).toEqual(["live"]);
  });

  it("does not treat a pre-kickoff 0.0 as a score", () => {
    const model = playerCardFromStarter({ ...base, game_status: "scheduled", game_started: false, actual_points: 0 });
    expect(model.points).toBeNull();
    expect(headlinePoints(model)).toEqual({ value: 14, kind: "proj" });
    expect(playerStatusChips(model)[0].kind).toBe("upcoming");
    expect(playerGameLine(model, "UTC")).toContain("DAL");
  });

  it("shows final score with result and FINAL chip", () => {
    const model = playerCardFromStarter({
      ...base,
      game_status: "final",
      game_started: true,
      actual_points: 20.4,
      game_is_home: true,
      game_team_score: 24,
      game_opponent_score: 17,
    });
    expect(playerGameLine(model)).toBe("vs DAL · Final 24-17 W");
    expect(playerStatusChips(model)[0]).toMatchObject({ kind: "final", tone: "muted" });
    expect(model.expectedFinal).toBe(20.4);
    expect(model.progress).toBe(1);
  });

  it("flags bye, out and questionable", () => {
    const bye = playerCardFromStarter({ ...base, projection: { status: "bye_week", point_estimate: null } });
    expect(playerStatusChips(bye).map((chip) => chip.kind)).toEqual(["bye"]);
    expect(playerGameLine(bye)).toBe("Bye week");
    expect(headlinePoints(bye).value).toBeNull();
    const out = playerCardFromStarter({ ...base, injury_label: "Out", game_status: "scheduled" });
    expect(playerStatusChips(out).map((chip) => chip.kind)).toEqual(["out"]);
    // A player ruled out is not projected any points, same as a bye.
    const outWithProjection = playerCardFromStarter({ ...base, injury_label: "Out", game_status: "scheduled", projection: { status: "ok", point_estimate: 14.2 } });
    expect(outWithProjection.projection).toBeNull();
    expect(outWithProjection.expectedFinal).toBe(0);
    expect(headlinePoints(outWithProjection).value).toBeNull();
    const questionable = playerCardFromStarter({ ...base, injury_label: "Questionable", game_status: "scheduled" });
    expect(playerStatusChips(questionable).map((chip) => chip.kind)).toEqual(["upcoming", "questionable"]);
  });

  it("trend compares projected final / final points against the projection", () => {
    expect(trendVsProjection(playerCardFromStarter(live))).toEqual({ dir: "up", delta: 3.4 });
    const down = playerCardFromStarter({ ...live, projected_final: 9 });
    expect(trendVsProjection(down)).toEqual({ dir: "down", delta: -5 });
    const flat = playerCardFromStarter({ ...live, projected_final: 14.4 });
    expect(trendVsProjection(flat)?.dir).toBe("flat");
    expect(trendVsProjection(playerCardFromStarter({ ...base, game_status: "scheduled" }))).toBeNull();
  });

  it("estimates quarters from progress", () => {
    expect(estimatedQuarter(0.05)).toBe("~Q1");
    expect(estimatedQuarter(0.3)).toBe("~Q2");
    expect(estimatedQuarter(0.99)).toBe("~Q4");
  });

  it("has an accessible summary", () => {
    expect(playerCardAriaLabel(playerCardFromStarter(live))).toContain("projected final 17.4");
  });
});

describe("real game clock on the card", () => {
  const qb: PlayerCardSource = { ...live, position: "QB", game_opponent: "IND", game_is_home: true, game_team_score: 14, game_opponent_score: 3, game_clock_label: "Q2 5:54", game_situation: "2nd & 7 at HOU 25", stats: { pass_att: 14, pass_cmp: 11, pass_yd: 118, pass_td: 2, pass_int: 2, rush_att: 1, rush_yd: 4 } };
  it("inline status uses the real clock and own score first; wall-clock estimate only as fallback", () => {
    expect(playerGameStatusLine(playerCardFromStarter(qb))).toBe("Q2 5:54 \u00b7 14-3 vs IND");
    expect(playerGameStatusLine(playerCardFromStarter({ ...qb, game_clock_label: null }))).toMatch(/^~Q\d/);
    expect(playerGameLine(playerCardFromStarter(qb))).toContain("Q2 5:54");
  });
  it("halftime, final, not started, bye", () => {
    expect(playerGameStatusLine(playerCardFromStarter({ ...qb, game_clock_label: "Half" }))).toMatch(/^Half/);
    expect(playerGameStatusLine(playerCardFromStarter({ ...qb, game_status: "final", game_clock_label: "Final" }))).toBe("Final 14-3 W");
    expect(playerGameStatusLine(playerCardFromStarter({ ...base, game_status: "scheduled", game_started: false, game_opponent: "MIN", game_kickoff_at: "2026-11-22T19:20:00-05:00" }), "America/New_York")).toBe("Sun 7:20 PM vs MIN");
    expect(playerGameStatusLine(playerCardFromStarter({ ...base, projection: { status: "bye_week", point_estimate: null } }))).toBe("Bye");
  });
  it("live stat line by position, only while his game is live or final", () => {
    expect(playerCardFromStarter(qb).statLine).toBe("11/14 CMP, 118 YD, 2 TD, 2 INT, 1 CAR, 4 YD");
    expect(playerCardFromStarter({ ...qb, game_status: "scheduled", game_started: false }).statLine).toBeNull();
    expect(liveStatLine({ rush_att: 6, rush_yd: 14, rec: 1, rec_tgt: 2, rec_yd: -1 }, "RB")).toBe("6 CAR, 14 YD, 1/2 REC, -1 YD");
    expect(liveStatLine({ rec: 2, rec_tgt: 3, rec_yd: 48, rec_td: 1 }, "WR")).toBe("2/3 REC, 48 YD, 1 TD");
    expect(liveStatLine({}, "WR")).toBeNull();
  });
  it("below projection is flat/down data only (UI keeps it muted); exited keeps projected final = actual from the server", () => {
    const m = playerCardFromStarter({ ...qb, projected_final: 8, projection: { status: "ok", point_estimate: 19, opponent: "IND" } });
    expect(trendVsProjection(m)?.dir).toBe("down");
  });
});
