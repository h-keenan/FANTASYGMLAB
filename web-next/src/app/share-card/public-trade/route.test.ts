// @vitest-environment node
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clearShareCachesForTests } from "@/lib/shareCard/server";
import { pngSize } from "@/lib/shareCard/testFixtures";
import type { TradeBoard } from "@/lib/seo/tradeAnalyzer";

import { GET } from "./route";

const BOARD: TradeBoard = {
  updated: "2026-10-27",
  tepAvailable: true,
  players: [
    { id: "1", name: "Star WR", pos: "WR", team: "MIN", age: 25, inj: null, v: [9000, 9100, 9200, 9300] },
    { id: "2", name: "Solid RB", pos: "RB", team: "SF", age: 27, inj: null, v: [5000, 5100, 5200, 5300] },
    { id: "3", name: "Depth TE", pos: "TE", team: "KC", age: 30, inj: "Questionable", v: [2000, 2100, 2200, 2300] },
  ],
};

const loadTradeBoard = vi.hoisted(() => vi.fn());
vi.mock("@/lib/seo/tradeBoardServer", () => ({ loadTradeBoard }));

const get = (query: string) => GET(new Request(`http://localhost/share-card/public-trade${query}`));

describe("GET /share-card/public-trade", () => {
  beforeEach(() => {
    clearShareCachesForTests();
    loadTradeBoard.mockReset();
    loadTradeBoard.mockResolvedValue(BOARD);
  });

  it("draws a public 1200x630 card for an entered trade, with no credentials", async () => {
    const response = await get("?a=1&b=2,3&f=sf");
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("cache-control")).toContain("public");
    expect(pngSize(await response.arrayBuffer())).toEqual({ width: 1200, height: 630, isPng: true });
  }, 60_000);

  it("rejects a trade with an empty side", async () => {
    expect((await get("?a=1")).status).toBe(422);
    expect((await get("")).status).toBe(422);
    expect(loadTradeBoard).not.toHaveBeenCalled();
  });

  it("404s ids that are not on the public board instead of drawing a made-up card", async () => {
    expect((await get("?a=999&b=2")).status).toBe(404);
  });

  it("reports an unavailable value board as 503", async () => {
    loadTradeBoard.mockRejectedValue(new Error("down"));
    expect((await get("?a=1&b=2")).status).toBe(503);
  });

  it("serves a repeat request from the render cache without reloading the board", async () => {
    await get("?a=1&b=2");
    const second = await get("?a=1&b=2");
    expect(second.headers.get("x-share-card-cache")).toBe("hit");
    expect(loadTradeBoard).toHaveBeenCalledTimes(1);
  }, 60_000);
});
