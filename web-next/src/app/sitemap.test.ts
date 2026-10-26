import { afterEach, describe, expect, it, vi } from "vitest";

import sitemap from "./sitemap";

const BASE = "https://app.fantasygmlab.com";

function jsonResponse(body: unknown) {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe("sitemap SEO entries", () => {
  afterEach(() => vi.restoreAllMocks());

  it("lists hub, rankings, chart and top-300 player pages when values load", async () => {
    const players = [
      { player_id: "1", name: "Top Guy", position: "RB", score: 9000, overall_rank: 1, position_rank: 1 },
      { player_id: "2", name: "Deep Cut", position: "WR", score: 1000, overall_rank: 450, position_rank: 70 },
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ format: "1qb", players, source_updated_at: "2026-10-25T00:00:00Z" }),
    );
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls).toContain(`${BASE}/dynasty-tools`);
    expect(urls).toContain(`${BASE}/dynasty-rankings/te`);
    expect(urls).toContain(`${BASE}/dynasty-trade-value-chart`);
    expect(urls).toContain(`${BASE}/dynasty-players/top-guy`);
    expect(urls).not.toContain(`${BASE}/dynasty-players/deep-cut`);
  });

  it("omits data-backed URLs (never placeholders) when the API is down", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const urls = (await sitemap()).map((e) => e.url);
    expect(urls).toContain(`${BASE}/dynasty-tools`);
    expect(urls.some((u) => u.includes("/dynasty-players/") || u.includes("/dynasty-rankings/"))).toBe(false);
    expect(urls.some((u) => u.includes("/dynasty-trade-value-chart"))).toBe(false);
  });
});
