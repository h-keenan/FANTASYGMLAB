import { describe, expect, it } from "vitest";

import { rosterOwnershipFrom, tradeShortcutsFor } from "./tradeShortcuts";

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
