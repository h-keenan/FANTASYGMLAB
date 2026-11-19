import { describe, expect, it } from "vitest";

import { SIM_CELEBRATIONS_KEY, simCelebrationsParse, simCelebrationsSerialize, simMomentShortName, simPickBoardNote, simPickMomentGrade, simStreakNumber, simWeekStamp } from "./simMoments";

const starter = (name: string, pts: number) => ({ player: { name }, pts, flag: null });

describe("Sim moments lib", () => {
  it("Celebrations defaults to on and only an explicit off turns it off", () => {
    expect(SIM_CELEBRATIONS_KEY).toBe("fd.sim.celebrations");
    expect(simCelebrationsParse(null)).toBe(true);
    expect(simCelebrationsParse("garbage")).toBe(true);
    expect(simCelebrationsParse(simCelebrationsSerialize(false))).toBe(false);
    expect(simCelebrationsParse(simCelebrationsSerialize(true))).toBe(true);
  });

  it("grades a pick by value over his slot, never below a C- and never a failing grade", () => {
    expect(simPickMomentGrade(6)).toMatchObject({ letter: "A-", line: "+6 over his slot", tone: "good" });
    expect(simPickMomentGrade(0).line).toBe("Right on his slot");
    expect(simPickMomentGrade(-6).line).toBe("6 under his slot");
    for (const v of [-80, -20, -10, -2, 0, 3, 8, 30, null, undefined]) expect(simPickMomentGrade(v).letter).toMatch(/^[ABC]/);
    expect(simPickBoardNote(6)).toBe("+6 slots");
    expect(simPickBoardNote(0)).toBe("Fair");
  });

  it("win stamp: record, movement and the top scorer as J. Surname", () => {
    const stamp = simWeekStamp({
      your_game: { result: "win", your_pts: 112.4, opp_pts: 98.1, opponent_name: "Gridiron Ghosts", optimal_pts: 118, starters: [starter("Jalen Pruitt", 31.4), starter("Marcus Hale", 12)] },
      standings: [{ is_you: true, wins: 4, losses: 2, rank: 3, rank_prev: 5 }],
    });
    expect(stamp).toMatchObject({ letter: "W", tone: "good", caption: "4-2, up to 3rd", note: "J. Pruitt led you with 31.4" });
  });

  it("loss stamp: still 5th, and a close loss blames the bench", () => {
    const stamp = simWeekStamp({
      your_game: { result: "loss", your_pts: 84.7, opp_pts: 101.9, optimal_pts: 101.9 + 0.1 + 0, starters: [starter("A B", 20)] },
      standings: [{ is_you: true, wins: 3, losses: 3, rank: 5, rank_prev: 5 }],
    });
    expect(stamp?.caption).toBe("3-3, still 5th");
    expect(stamp?.letter).toBe("L");
    const close = simWeekStamp({ your_game: { result: "loss", your_pts: 84.7, opp_pts: 90, optimal_pts: 101.9, starters: [] }, standings: [] });
    expect(close?.note).toBe("Close one, 17.2 points sat on your bench");
    expect(simWeekStamp({ your_game: null })).toBeNull();
  });

  it("a streak badge shows its count; no other badge does", () => {
    expect(simStreakNumber({ key: "win_streak", detail: "5 wins in a row (through week 7)." })).toBe(5);
    expect(simStreakNumber({ key: "loss_streak", detail: "8 losses in a row.", tier: 8 })).toBe(8);
    expect(simStreakNumber({ key: "closest_win", detail: "Won by just 0.4" })).toBeNull();
    expect(simMomentShortName("Marvin Harrison Jr.")).toBe("M. Harrison Jr.");
  });
});
