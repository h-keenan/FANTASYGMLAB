import { afterEach, describe, expect, it, vi } from "vitest";

import { GET } from "./route";

function board(format: string, tep: boolean, score: number) {
  return {
    format,
    tep,
    source_updated_at: "2026-10-27T00:00:00Z",
    players: [{ player_id: "1", name: "A", position: "WR", score, overall_rank: 1, position_rank: 1 }],
  };
}

describe("GET /api/public-trade-values", () => {
  afterEach(() => vi.restoreAllMocks());

  it("merges the four boards into one compact, cacheable payload", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      const sf = url.includes("format=superflex");
      const tep = url.includes("tep=true");
      return { ok: true, status: 200, json: async () => board(sf ? "superflex" : "1qb", tep, (sf ? 200 : 100) + (tep ? 10 : 0)) } as Response;
    });
    const response = await GET();
    expect(response.status).toBe(200);
    expect(response.headers.get("Cache-Control")).toContain("s-maxage");
    const body = await response.json();
    expect(body.tepAvailable).toBe(true);
    expect(body.players[0].v).toEqual([100, 200, 110, 210]);
  });

  it("falls back to no-TEP when the premium boards fail, and 503s when values are down", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (String(input).includes("tep=true")) throw new Error("boom");
      return { ok: true, status: 200, json: async () => board(String(input).includes("superflex") ? "superflex" : "1qb", false, 100) } as Response;
    });
    expect((await (await GET()).json()).tepAvailable).toBe(false);

    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("down"));
    expect((await GET()).status).toBe(503);
  });
});
