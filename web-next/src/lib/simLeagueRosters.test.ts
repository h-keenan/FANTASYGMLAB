import { describe, expect, it } from "vitest";

import { simBlockEntryCount, simBlockNote, simGroupBenchByPosition, simRosterEntries, simRosterPositions, simTeamChips, simTeamRecordLine } from "./simLeagueRosters";
import type { SimGamePlayer, SimLeagueRosterTeam } from "./simGame";

const pl = (id: string, pos: SimGamePlayer["pos"], name: string, value: number, team = "KC") => ({ id, pos, name, value, team, ros_mean: value / 10, projection: 10, status: "healthy" }) as unknown as SimGamePlayer;
const t = (id: string, players: SimGamePlayer[]) => ({ team_id: id, name: `T${id}`, is_you: false, players }) as unknown as SimLeagueRosterTeam;

describe("league roster helpers", () => {
  it("filters by position and search and sorts best overall (then value) first across teams", () => {
    const teams = [t("1", [pl("a", "QB", "Alpha", 50), pl("b", "RB", "Bravo", 90)]), t("2", [pl("c", "QB", "Charlie", 70, "BUF")])];
    expect(simRosterEntries(teams, "ALL", "").map((e) => e.player.id)).toEqual(["b", "c", "a"]);
    expect(simRosterEntries(teams, "QB", "").map((e) => [e.player.id, e.team.team_id])).toEqual([["c", "2"], ["a", "1"]]);
    expect(simRosterEntries(teams, "ALL", "buf").map((e) => e.player.id)).toEqual(["c"]);
    expect(simRosterPositions(teams)).toEqual(["QB", "RB"]);
  });
  it("chips, record line and value label", () => {
    expect(simTeamChips({ needs: ["QB"], surplus: ["RB", "WR"] }).map((c) => c.label)).toEqual(["Needs QB", "Deep RB", "Deep WR"]);
    const rec = (w: number, l: number) => ({ record: { wins: w, losses: l, ties: 0, pf: 10, pa: 9, rank: 2 }, power_rank: 4 }) as never;
    expect(simTeamRecordLine(rec(3, 0))).toBe("3-0 · #2 · 10.0 PF");
    expect(simTeamRecordLine(rec(0, 0))).toBe("0-0 · Power #4");
    expect(simTeamRecordLine({ record: null, power_rank: 4 })).toBe("Power #4");
  });
  it("groups the bench by position", () => {
    const g = simGroupBenchByPosition([pl("a", "WR", "A", 1), pl("b", "QB", "B", 1), pl("c", "WR", "C", 1)], ["QB", "RB", "WR"]);
    expect(g.map((x) => [x.pos, x.players.length])).toEqual([["QB", 1], ["WR", 2]]);
  });
  it("filters to what is on a trade block and notes what the team says about itself", () => {
    const withBlock = (p: SimGamePlayer): SimGamePlayer => ({ ...p, block: { by: "1", mine: false, looking_for: "RB", why: "Selling depth" } });
    const teams = [
      { ...t("1", [withBlock(pl("a", "QB", "Alpha", 50)), pl("b", "RB", "Bravo", 90)]), needs: ["RB", "WR"], block: { stance: "contending", looking_for: "RB", items: [{ id: "a", why: "Selling depth" }] } },
      t("2", [pl("c", "QB", "Charlie", 70)]),
    ] as unknown as SimLeagueRosterTeam[];
    expect(simRosterEntries(teams, "ALL", "", true).map((e) => e.player.id)).toEqual(["a"]);
    expect(simRosterEntries(teams, "RB", "", true)).toEqual([]);
    expect(simBlockEntryCount(teams)).toBe(1);
    expect(simBlockNote(teams[0], "Selling depth")).toBe("Selling depth · looking for RB · needs RB, WR");
    expect(simBlockNote({ needs: [] }, undefined)).toBe("");
  });
});
