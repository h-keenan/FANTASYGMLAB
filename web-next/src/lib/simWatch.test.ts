import { describe, expect, it } from "vitest";

import { SIM_WATCH_DEFAULTS, normalizeWatchReport, simWatchMoves, simWatchShortName, simWatchGradeMove, simWatchPlaybackLine, simWatchRerunBody, simWatchSliders } from "./simWatch";
import { simSetupBody, simSetupDefaults } from "./simGame";

describe("Draft & Watch lib", () => {
  it("defaults are Balanced waivers and Light trades", () => {
    expect(SIM_WATCH_DEFAULTS).toEqual({ waivers: "balanced", trades: "light" });
    expect(simSetupDefaults(null).watch).toBe(false);
  });

  it("the setup body sends watch only for a fresh redraft and forces auto lineup", () => {
    const base = { ...simSetupDefaults(null), watch: true, watchWaivers: "aggressive", watchTrades: "off", auto: false };
    const body = simSetupBody(base);
    expect(body).toMatchObject({ watch: true, watch_waivers: "aggressive", watch_trades: "off", auto_lineup: true });
    expect(simSetupBody({ ...base, watch: false })).not.toHaveProperty("watch");
    expect(simSetupBody({ ...base, mode: "dynasty" })).not.toHaveProperty("watch");
  });

  it("reads the sliders off a game's settings, null for an ordinary game", () => {
    expect(simWatchSliders({})).toBeNull();
    expect(simWatchSliders({ watch_v: 1, watch_waivers: "hands_off", watch_trades: "active" })).toEqual({ waivers: "hands_off", trades: "active" });
    expect(simWatchSliders({ watch_v: 1, watch_waivers: "junk" })?.waivers).toBe("balanced");
  });

  it("rerun body keeps the league and the slot only for Run it back", () => {
    const settings = { watch_v: 1, watch_waivers: "balanced", watch_trades: "light", teams: 10, scoring: "ppr", user_slot: 4 };
    expect(simWatchRerunBody(settings, true)).toMatchObject({ watch: true, teams: 10, user_slot: 4 });
    expect(simWatchRerunBody(settings, false)).toMatchObject({ user_slot: null });
  });

  it("playback lines read a recap and never show red", () => {
    const line = simWatchPlaybackLine({ week: 3, kind: "regular", your_game: { result: "win", your_pts: 112.4, opp_pts: 98.1, opponent_name: "Harbor Hawks" }, standings: [{ is_you: true, rank: 2 }] });
    expect(line).toMatchObject({ week: 3, text: "Wk 3 · W 112.4-98.1 vs Harbor Hawks · 2nd", result: "W", label: "Wk 3 vs Harbor Hawks", score: "112.4 - 98.1" });
    expect(simWatchPlaybackLine({ week: 6, your_game: null })?.text).toBe("Wk 6 · bye");
    expect(simWatchPlaybackLine(null)).toBeNull();
  });

  it("grade move and report parsing", () => {
    expect(simWatchGradeMove("B", "A-")).toBe("up");
    expect(simWatchGradeMove("A", "C")).toBe("down");
    expect(simWatchGradeMove(null, "C")).toBe("same");
    expect(normalizeWatchReport({})).toBeNull();
    const report = normalizeWatchReport({
      sliders: { waivers: "balanced", trades: "light" },
      standing: { rank: 3, teams: 12, record: "9-5", outcome: "semifinal" },
      draft: { then: { grade: "B", rank: 4 }, now: { grade: "C+", rank: 7, points: 900 }, teams: 12 },
      bust: { player: { id: "1", name: "Marcus Hale", pos: "RB", team: "MIA" }, pick: "Round 2, pick 17", projected: 168, actual: 115.6, gap: -52.4, why: "Missed 5 games: hamstring", why_tag: "injury", games_missed: 5 },
      moves: { waivers: 4, trades: 1 },
      what_ifs: [{ id: "a", title: "T", delta: 10, text: "x", players: [] }],
    });
    expect(report?.bust?.why).toBe("Missed 5 games: hamstring");
    expect(report?.best_value).toBeNull();
    expect(report?.what_ifs).toHaveLength(1);
  });

  it("moves we made are the user's adds that went through, with short names", () => {
    const recap = { waivers: [{ team_id: "me", ok: true, add: { name: "Rafael Duke" }, drop: { name: "Marcus Hale" } }, { team_id: "me", ok: false, add: { name: "Nope Nobody" } }, { team_id: "x", ok: true, add: { name: "Other Team" } }] };
    expect(simWatchMoves(recap, "me")).toEqual([{ title: "Added R. Duke", sub: "Dropped M. Hale" }]);
    expect(simWatchShortName("Marvin Harrison Jr.")).toBe("M. Harrison Jr.");
  });
});
