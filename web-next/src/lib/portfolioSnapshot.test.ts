import { describe, expect, it } from "vitest";

import type { PortfolioIndexResponse, PortfolioLeague, PortfolioLeagueResponse } from "@/lib/api";
import { PORTFOLIO_FRESH_MS } from "@/lib/portfolioLoader";
import {
  buildPortfolioSnapshot,
  clearPortfolioSnapshots,
  parsePortfolioSnapshot,
  planFromSnapshot,
  PORTFOLIO_SNAPSHOT_MAX_AGE_MS,
  portfolioSnapshotKey,
  readPortfolioSnapshot,
  writePortfolioSnapshot,
} from "@/lib/portfolioSnapshot";

const NOW = 1_800_000_000_000;
const INDEX: PortfolioIndexResponse = {
  ok: true,
  is_premium: true,
  lens: "Dynasty",
  leagues: [],
  failed_leagues: [],
  upsell: null,
  saved_leagues: [
    { league_id: "a", league_name: "Alpha" },
    { league_id: "b", league_name: "Bravo" },
    { league_id: "c", league_name: "Charlie" },
  ],
};

function response(id: string, extra: Partial<PortfolioLeagueResponse> = {}): PortfolioLeagueResponse {
  return {
    ok: true,
    is_premium: true,
    lens: "Dynasty",
    league: { league_id: id, league_name: id } as PortfolioLeague,
    failed_league: null,
    upsell: null,
    ...extra,
  };
}

function memoryStorage(initial: Record<string, string> = {}) {
  const data = new Map(Object.entries(initial));
  return {
    get length() {
      return data.size;
    },
    key: (i: number) => [...data.keys()][i] ?? null,
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
}

describe("portfolio snapshot", () => {
  it("stores only complete rows: never a headline-first row, a failure or a pending league", () => {
    const snapshot = buildPortfolioSnapshot(
      INDEX,
      {
        a: { status: "success", data: response("a") },
        b: { status: "success", data: response("b", { signals_pending: true }) },
        c: { status: "error" },
      },
      { a: NOW - 5 },
      null,
      NOW,
    );
    expect(Object.keys(snapshot?.rows ?? {})).toEqual(["a"]);
    expect(snapshot?.rows.a.at).toBe(NOW - 5);
  });

  it("keeps a previously stored row for a league not reloaded this visit", () => {
    const previous = { index: INDEX, rows: { c: { at: NOW - 1000, data: response("c") } } };
    const snapshot = buildPortfolioSnapshot(INDEX, { a: { status: "success", data: response("a") } }, {}, previous, NOW);
    expect(Object.keys(snapshot?.rows ?? {}).sort()).toEqual(["a", "c"]);
    expect(snapshot?.rows.c.at).toBe(NOW - 1000);
  });

  it("stores nothing for a Free index or when no row is complete", () => {
    expect(buildPortfolioSnapshot({ ...INDEX, is_premium: false }, {}, {}, null, NOW)).toBeNull();
    expect(buildPortfolioSnapshot(INDEX, { a: { status: "pending" } }, {}, null, NOW)).toBeNull();
  });

  it("round-trips through storage per user and lens, and ignores rows older than a day", () => {
    const storage = memoryStorage();
    const snapshot = {
      index: INDEX,
      rows: {
        a: { at: NOW - 1000, data: response("a") },
        b: { at: NOW - PORTFOLIO_SNAPSHOT_MAX_AGE_MS - 1, data: response("b") },
      },
    };
    writePortfolioSnapshot(storage, "u1", "Dynasty", snapshot);
    const read = readPortfolioSnapshot(storage, "u1", "Dynasty", NOW);
    expect(Object.keys(read?.rows ?? {})).toEqual(["a"]);
    expect(readPortfolioSnapshot(storage, "u2", "Dynasty", NOW)).toBeNull();
    expect(readPortfolioSnapshot(storage, "u1", "Redraft", NOW)).toBeNull();
    writePortfolioSnapshot(storage, "u1", "Dynasty", null);
    expect(storage.getItem(portfolioSnapshotKey("u1", "Dynasty"))).toBeNull();
  });

  it("treats garbage, a Free snapshot and a quota error as no snapshot", () => {
    expect(parsePortfolioSnapshot("{not json", NOW)).toBeNull();
    expect(parsePortfolioSnapshot(JSON.stringify({ index: { ...INDEX, is_premium: false }, rows: {} }), NOW)).toBeNull();
    const throwing = {
      length: 0,
      key: () => null,
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("quota");
      },
      removeItem: () => undefined,
    };
    expect(readPortfolioSnapshot(throwing, "u", "Dynasty", NOW)).toBeNull();
    expect(() => writePortfolioSnapshot(throwing, "u", "Dynasty", { index: INDEX, rows: {} })).not.toThrow();
  });

  it("paints stored leagues, revalidates stale ones, leaves fresh ones, and starts the rest pending", () => {
    const snapshot = {
      index: INDEX,
      rows: {
        a: { at: NOW - PORTFOLIO_FRESH_MS - 1, data: response("a") },
        b: { at: NOW - 1000, data: response("b") },
      },
    };
    const plan = planFromSnapshot(snapshot, ["a", "b", "c", "d"], NOW);
    expect(plan.warm).toEqual(["a"]);
    expect(plan.skip).toEqual(["b"]);
    expect(plan.states.a.status).toBe("success");
    expect(plan.states.b.status).toBe("success");
    expect(plan.states.c).toEqual({ status: "pending" });
    expect(plan.states.d).toEqual({ status: "pending" });
    // A league the index no longer lists simply is not planned.
    expect(Object.keys(planFromSnapshot(snapshot, ["b"], NOW).states)).toEqual(["b"]);
  });

  it("clears every user's Portfolio snapshot on sign-out and nothing else", () => {
    const storage = memoryStorage({
      [portfolioSnapshotKey("u1", "Dynasty")]: "x",
      [portfolioSnapshotKey("u2", "Dynasty")]: "y",
      "fd:other": "keep",
    });
    clearPortfolioSnapshots(storage);
    expect(storage.length).toBe(1);
    expect(storage.getItem("fd:other")).toBe("keep");
  });
});
