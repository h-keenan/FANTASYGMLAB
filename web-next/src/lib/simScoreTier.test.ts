import { describe, expect, it } from "vitest";

import { simCareerSeasonParts } from "./simHistory";
import { simRankTier, simScoreTierTone, simSeasonTier, simWeekTier } from "./simScoreTier";

describe("sim score tiers vs the position's normal", () => {
  it("the same score reads differently by position", () => {
    expect(simWeekTier(17.5, "RB")).toBe("boom");
    expect(simWeekTier(17.5, "QB")).toBe("average");
    expect(simWeekTier(2, "WR")).toBe("bust");
    expect(simWeekTier(11, "WR")).toBe("average");
  });
  it("season rate and rank tiers", () => {
    expect(simSeasonTier(15, "WR")).toBe("boom");
    expect(simSeasonTier(6, "WR")).toBe("bust");
    expect(simSeasonTier(null, "WR")).toBe("average");
    expect(simRankTier(3, "WR")).toBe("boom");
    expect(simRankTier(18, "WR")).toBe("average");
    expect(simRankTier(40, "WR")).toBe("bust");
  });
  it("maps to semantic tones only (average stays neutral)", () => {
    expect(simScoreTierTone("boom")).toBe("success");
    expect(simScoreTierTone("bust")).toBe("warning");
    expect(simScoreTierTone("average")).toBeUndefined();
  });
  it("season summary parts carry the tone", () => {
    const parts = simCareerSeasonParts({ season: 1, year: 2026, games: 14, points: 210, ppg: 15, pos: "WR", pos_rank: 4 });
    expect(parts.find((p) => p.key === "pts")?.tone).toBe("success");
    expect(parts.find((p) => p.key === "rank")?.tone).toBe("success");
    expect(parts.find((p) => p.key === "games")?.tone).toBeUndefined();
  });
});
