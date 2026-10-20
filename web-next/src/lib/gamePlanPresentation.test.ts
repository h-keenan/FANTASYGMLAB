import { describe, expect, it } from "vitest";

import { gamePlanTileHref, resolveGamePlanTargetPlayerId } from "./gamePlanPresentation";

describe("resolveGamePlanTargetPlayerId", () => {
  it("prefers route_player_id when present", () => {
    const item = {
      route_player_id: "4046",
      presentation: { trade_package: { receive: [{ player_id: "2" }] } },
    };
    expect(resolveGamePlanTargetPlayerId(item)).toBe("4046");
  });

  // coridian_, 2026-10-18: "Top priority still has no player card" — a Top
  // Trade Opportunity tile can arrive with route_player_id empty but a real
  // give/get package (see GamePlanCard.test.tsx/BriefingItemPlayers' own
  // precedent for this same fallback).
  it("falls back to the trade package's headline receive player when route_player_id is empty", () => {
    const item = {
      route_player_id: "",
      presentation: {
        trade_package: {
          receive: [
            { player_id: "" }, // a pick, no player_id
            { player_id: "2" },
          ],
        },
      },
    };
    expect(resolveGamePlanTargetPlayerId(item)).toBe("2");
  });

  it("returns empty when there is no route player and no trade package", () => {
    expect(resolveGamePlanTargetPlayerId({ route_player_id: "", presentation: null })).toBe("");
  });
});

describe("gamePlanTileHref", () => {
  it("builds the plain league href when there is no target player", () => {
    expect(gamePlanTileHref("waivers", "abc", "Revivalry", "")).toBe("/waivers/abc?name=Revivalry");
  });

  it("appends playerId when a target player is known", () => {
    expect(gamePlanTileHref("trade-hub", "abc", "Revivalry", "4046")).toBe("/trade-hub/abc?name=Revivalry&playerId=4046");
  });

  it("encodes a league id that needs escaping", () => {
    expect(gamePlanTileHref("waivers", "a/b", "Revivalry", "")).toBe("/waivers/a%2Fb?name=Revivalry");
  });
});
