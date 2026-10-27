import { describe, expect, it, vi } from "vitest";

import type { RankedPlayer } from "@/lib/api";

import {
  analyzerBridgePath,
  bridgeNotice,
  bridgePickerPath,
  bridgeTradeFromSearch,
  clearPendingBridge,
  readPendingBridge,
  resolveBridgeTrade,
  sanitizeBridgeTrade,
  storePendingBridge,
} from "./tradeBridge";

const player = (player_id: string, name: string) => ({ player_id, name, position: "WR" }) as unknown as RankedPlayer;
const RANKINGS = [player("1", "Mine WR"), player("2", "Theirs RB"), player("3", "Theirs WR"), player("4", "Other Team QB"), player("5", "Free Agent")];
const MINE = new Set(["1"]);
const TEAMS = [
  { rosterId: "7", playerIds: new Set(["2", "3"]) },
  { rosterId: "8", playerIds: new Set(["4"]) },
];

function memory() {
  const data = new Map<string, string>();
  return {
    setItem: (k: string, v: string) => void data.set(k, v),
    getItem: (k: string) => data.get(k) ?? null,
    removeItem: (k: string) => void data.delete(k),
  };
}

describe("pending bridge storage", () => {
  it("round-trips a validated trade and expires after a day", () => {
    const storage = memory();
    storePendingBridge(storage, { a: ["1"], b: ["2", "3"] }, 1_000);
    expect(readPendingBridge(storage, 2_000)).toEqual({ a: ["1"], b: ["2", "3"] });
    expect(readPendingBridge(storage, 1_000 + 25 * 60 * 60 * 1000)).toBeNull();
    clearPendingBridge(storage);
    expect(readPendingBridge(storage, 2_000)).toBeNull();
  });

  it("refuses unsafe ids and incomplete trades", () => {
    const storage = memory();
    storePendingBridge(storage, { a: ["1"], b: [] });
    storePendingBridge(storage, { a: ["../x"], b: ["<script>"] });
    expect(readPendingBridge(storage)).toBeNull();
    expect(sanitizeBridgeTrade({ a: ["1", "1", "2"], b: ["2", "3"] })).toEqual({ a: ["1", "2"], b: ["3"] });
  });

  it("survives broken storage", () => {
    const broken = { setItem: vi.fn(() => { throw new Error("blocked"); }), getItem: vi.fn(() => { throw new Error("blocked"); }) };
    expect(() => storePendingBridge(broken, { a: ["1"], b: ["2"] })).not.toThrow();
    expect(readPendingBridge(broken)).toBeNull();
  });
});

describe("bridge paths", () => {
  it("carries the trade into the league analyzer and the picker", () => {
    const trade = { a: ["1"], b: ["2", "3"] };
    expect(analyzerBridgePath("L 1", "My League", trade)).toBe("/trade-analyzer/L%201?name=My+League&a=1&b=2,3");
    expect(bridgePickerPath(trade)).toBe("/trade-analyzer/bridge?a=1&b=2,3");
    expect(bridgeTradeFromSearch("?a=1&b=2,3&f=sf")).toEqual(trade);
    expect(bridgeTradeFromSearch("?a=1")).toBeNull();
  });
});

describe("resolveBridgeTrade", () => {
  const run = (a: string[], b: string[]) =>
    resolveBridgeTrade({ trade: { a, b }, rankings: RANKINGS, myRosterIds: MINE, otherTeams: TEAMS });

  it("fills send from my roster and receive from one partner", () => {
    const result = run(["1"], ["2", "3"]);
    expect(result.send.map((p) => p.player_id)).toEqual(["1"]);
    expect(result.receive.map((p) => p.player_id)).toEqual(["2", "3"]);
    expect(result.partnerRosterId).toBe("7");
    expect(result.skipped).toEqual([]);
    expect(bridgeNotice(result)).toMatch(/Your public trade is loaded \(3 players\)/);
  });

  it("reports, rather than forces, players that do not fit", () => {
    const result = run(["2", "99"], ["3", "4", "5", "1"]);
    expect(result.send).toEqual([]);
    expect(result.receive.map((p) => p.player_id)).toEqual(["3"]);
    expect(result.skipped).toEqual([
      { name: "Theirs RB", reason: "not_on_your_roster" },
      { name: null, reason: "not_in_league" },
      { name: "Other Team QB", reason: "other_team" },
      { name: "Free Agent", reason: "not_on_a_roster" },
      { name: "Mine WR", reason: "already_yours" },
    ]);
    const notice = bridgeNotice(result);
    expect(notice).toMatch(/Loaded 1 of 6 players/);
    expect(notice).toMatch(/Theirs RB \(not on your roster\)/);
    expect(notice).toMatch(/A player \(not in this league's player pool\)/);
  });

  it("says so when nothing fits", () => {
    expect(bridgeNotice(run(["99"], ["98"]))).toMatch(/^None of the players/);
  });
});
