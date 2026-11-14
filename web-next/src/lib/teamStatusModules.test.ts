import { describe, expect, it } from "vitest";

import { collapsedVerdict } from "./moduleTemplates";
import { lineupModuleParts, roomsModuleParts, standingModuleParts, teamStatusHeroModel } from "./teamStatusModules";

const matchup = { week: 9, opponentName: "Rival FC", opponentAvatar: null, myName: "Me", myAvatar: null, winPercent: 63, myProjected: 101.3, opponentProjected: 96, live: null, stateLabel: null };
const standing = { record: "3-5", place: "3rd of 12", playoffStatus: null, powerRank: 2, playoffOdds: "41%", projectedRecord: "7-7", tone: "neutral" as const };

describe("teamStatusModules", () => {
  it("picks the one big number: win chance, then score, then standing, then nothing", () => {
    expect(teamStatusHeroModel(matchup, standing)).toMatchObject({ label: "Your win chance", value: "63%", tone: "success" });
    expect(teamStatusHeroModel({ ...matchup, winPercent: null, live: { mine: 80, opponent: 90 } }, standing)).toMatchObject({ label: "Score so far", tone: "danger" });
    expect(teamStatusHeroModel(null, standing)).toMatchObject({ label: "Standing", value: "3rd of 12" });
    expect(teamStatusHeroModel(null, { ...standing, place: null })).toMatchObject({ label: "Record", value: "3-5" });
    expect(teamStatusHeroModel(null, null)).toBeNull();
  });

  it("every module summary passes the collapsed-form rule", () => {
    expect(collapsedVerdict(lineupModuleParts({ tone: "risk", headline: "1 starter can't play (bye or out)", detail: null })).ok).toBe(true);
    expect(collapsedVerdict(standingModuleParts(standing)).summary).toBe("3rd of 12 · 3-5 · Playoff odds 41% · Proj 7-7");
    const rooms = roomsModuleParts([
      { position: "QB", label: "Strength", tone: "positive", weakest: false },
      { position: "RB", label: "Needs help", tone: "risk", weakest: true },
    ]);
    expect(rooms[0].text).toBe("RB Needs help");
    expect(collapsedVerdict(rooms).ok).toBe(true);
  });
});
