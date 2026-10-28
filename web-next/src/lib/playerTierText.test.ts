import { describe, expect, it } from "vitest";

import { tierTextLabel } from "./playerTier";
import { playerFacts } from "./seo/content";
import type { PublicBoard, PublicPlayer } from "./seo/publicValues";

describe("tier text vocabulary (audit C4)", () => {
  it("names stored tiers with the app's one ladder, never the stored word", () => {
    expect(tierTextLabel("Elite")).toBe("Generational");
    expect(tierTextLabel("Star")).toBe("Elite");
    expect(tierTextLabel("Core Starter")).toBe("Impact Starter");
    expect(tierTextLabel("Depth")).toBe("Committee / Role");
    expect(tierTextLabel("Workhorse")).toBeNull();
    expect(tierTextLabel(null)).toBeNull();
  });
  it("SEO player facts print the ladder name, so stored 'Elite' reads Generational like the player card", () => {
    const player = {
      player_id: "1", name: "Top Guy", position: "WR", team: "KC", age: 24, years_exp: 3, status: null,
      injury_status: null, score: 9000, overall_rank: 1, position_rank: 1, tier: "Elite", overall_rating: 99, trend: null,
    } as PublicPlayer;
    const board = { teams: 12, scoring: "PPR", players: [player] } as unknown as PublicBoard;
    const facts = playerFacts(player, board, null).join(" ");
    expect(facts).toContain("places him in the Generational tier");
    expect(facts).not.toContain("the Elite tier");
  });
});
