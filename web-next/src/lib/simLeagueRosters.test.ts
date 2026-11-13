import { describe, expect, it } from "vitest";

import { simGroupBenchByPosition, simOverallLabel, simRosterEntries, simRosterPositions, simTeamChips, simTeamRecordLine, simValueLabel } from "./simLeagueRosters";
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
    expect([0, 0.4, 71.6, null].map(simValueLabel)).toEqual(["—", "—", "72", "—"]);
  });
  it("labels overall and groups the bench by position", () => {
    expect([null, 0, 71.6].map(simOverallLabel)).toEqual(["—", "0", "72"]);
    const g = simGroupBenchByPosition([pl("a", "WR", "A", 1), pl("b", "QB", "B", 1), pl("c", "WR", "C", 1)], ["QB", "RB", "WR"]);
    expect(g.map((x) => [x.pos, x.players.length])).toEqual([["QB", 1], ["WR", 2]]);
  });
});
