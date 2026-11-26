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
    expect(urls).toContain(`${BASE}/trade-analyzer`); // static shell: listed even when the API is down
    expect(urls.some((u) => u.includes("/dynasty-players/") || u.includes("/dynasty-rankings/"))).toBe(false);
    expect(urls.some((u) => u.includes("/dynasty-trade-value-chart"))).toBe(false);
  });

  it("never stamps static routes as modified now; legal pages use their real last-updated date", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const entries = await sitemap();
    const byUrl = new Map(entries.map((e) => [e.url, e]));
    expect(byUrl.get(`${BASE}/premium`)?.lastModified).toBeUndefined();
    expect(byUrl.get(`${BASE}/`)?.lastModified).toBeUndefined();
    expect((byUrl.get(`${BASE}/legal/terms`)?.lastModified as Date).toISOString().slice(0, 10)).toBe("2026-10-21");
  });

  describe("season-gated pages", () => {
    const teams = Array.from({ length: 32 }, (_, i) => ({
      team: `T${i}`,
      confidence: "high",
      opponents: [{ week: 15, opponent: "X", is_home: true }],
      by_position: { QB: { avg_points_allowed: 18, vs_league_avg_pct: 1, rank_easiest: i + 1, of: 32 } },
    }));
    const rookies = Array.from({ length: 14 }, (_, i) => ({
      player_id: `r${i}`, name: `Rookie ${i}`, position: "WR", score: 5000 - i, overall_rank: 50 + i, position_rank: 10 + i, years_exp: 0,
    }));
    const board = { format: "1qb", players: [{ player_id: "1", name: "Top Guy", position: "RB", score: 9000, overall_rank: 1, position_rank: 1, years_exp: 5 }, ...rookies], source_updated_at: "2026-10-25T00:00:00Z" };
    const mockApi = () =>
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
        const url = String(input);
        if (url.includes("/v1/public/playoff-sos")) return jsonResponse({ status: "ok", generated_at: "2026-11-26T15:30:00Z", season: 2026, weeks: [15, 16, 17], teams });
        return jsonResponse(board);
      });

    afterEach(() => vi.useRealTimers());

    it("lists the playoff SOS page in weeks 9-17 with a day-precision lastModified, and no rookie page", async () => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date("2026-11-26T15:00:00Z"));
      mockApi();
      const entries = await sitemap();
      const sos = entries.find((e) => e.url === `${BASE}/fantasy-playoff-strength-of-schedule`);
      expect((sos?.lastModified as Date).toISOString()).toBe("2026-11-26T00:00:00.000Z");
      expect(entries.some((e) => e.url.includes("dynasty-rookie-rankings"))).toBe(false);
    });

    it("lists the rookie page after the draft, and no playoff page", async () => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date("2027-05-20T15:00:00Z"));
      mockApi();
      const urls = (await sitemap()).map((e) => e.url);
      expect(urls).toContain(`${BASE}/dynasty-rookie-rankings`);
      expect(urls.some((u) => u.includes("playoff-strength"))).toBe(false);
    });

    it("omits the playoff page when the API has no usable schedule", async () => {
      vi.useFakeTimers({ toFake: ["Date"] });
      vi.setSystemTime(new Date("2026-11-26T15:00:00Z"));
      vi.spyOn(globalThis, "fetch").mockImplementation(async (input) =>
        String(input).includes("/v1/public/playoff-sos")
          ? jsonResponse({ status: "unavailable", generated_at: "2026-11-26T15:30:00Z", season: 2026, weeks: [15, 16, 17], teams: [] })
          : jsonResponse(board),
      );
      expect((await sitemap()).some((e) => e.url.includes("playoff-strength"))).toBe(false);
    });
  });
});
