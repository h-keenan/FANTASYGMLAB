import { describe, expect, it } from "vitest";

import { playerLeagueStatus, playerLeagueStatusLabel, rosterOwnershipFrom, tradeShortcutsFor } from "./tradeShortcuts";

const ownership = rosterOwnershipFrom({ players: ["1", 2] }, [
  { roster_id: 1, players: ["1", "2"] },
  { roster_id: 2, players: ["3"] },
  { roster_id: 3, players: null },
]);

describe("tradeShortcutsFor", () => {
  it("gives own players both actions", () => {
    expect(tradeShortcutsFor("1", ownership)).toEqual({ canAddToTrade: true, canFindTrades: true });
  });
  it("gives other teams' players only Add to Trade", () => {
    expect(tradeShortcutsFor("3", ownership)).toEqual({ canAddToTrade: true, canFindTrades: false });
  });
  it("hides everything for free agents and unknown ownership", () => {
    expect(tradeShortcutsFor("99", ownership)).toEqual({ canAddToTrade: false, canFindTrades: false });
    expect(tradeShortcutsFor("1", null)).toEqual({ canAddToTrade: false, canFindTrades: false });
    expect(tradeShortcutsFor("", ownership)).toEqual({ canAddToTrade: false, canFindTrades: false });
  });
});

describe("playerLeagueStatus", () => {
  const leagueOwnership = rosterOwnershipFrom({ roster_id: 1, players: ["a"] }, [
    { roster_id: 1, players: ["a"] },
    { roster_id: 2, players: ["b"] },
  ]);

  it("is null until ownership is known", () => {
    expect(playerLeagueStatus("a", null)).toBeNull();
  });

  it("reports mine, rostered (with team name) and free agent", () => {
    expect(playerLeagueStatus("a", leagueOwnership)).toEqual({ kind: "mine" });
    expect(playerLeagueStatus("b", leagueOwnership, { "2": "Rival GM" })).toEqual({ kind: "rostered", teamName: "Rival GM" });
    expect(playerLeagueStatus("c", leagueOwnership)).toEqual({ kind: "free_agent" });
  });

  it("still reports a rostered player when no team name is known", () => {
    const status = playerLeagueStatus("b", leagueOwnership);
    expect(status).toEqual({ kind: "rostered", teamName: null });
    expect(playerLeagueStatusLabel(status!)).toBe("On another team");
  });
});
