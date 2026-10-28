import { describe, expect, it } from "vitest";

import {
  isPageEligible,
  isPlayerPageIndexable,
  isRankingsIndexable,
  MIN_RANKINGS_PLAYERS,
  neighbors,
  playerFacts,
  trendLabel,
} from "./content";
import { breadcrumbLd, serializeLd } from "./jsonld";
import { parseBoard, type PublicBoard, type PublicPlayer } from "./publicValues";
import { parsePosition } from "./site";
import { assignSlugs, findPlayerBySlug, slugify } from "./slug";

function player(over: Partial<PublicPlayer> = {}): PublicPlayer {
  return {
    player_id: "1",
    name: "Test Player",
    position: "WR",
    team: "KC",
    age: 25,
    years_exp: 3,
    status: "Active",
    injury_status: null,
    score: 8000,
    overall_rank: 5,
    position_rank: 2,
    tier: "Elite",
    overall_rating: 95,
    trend: "Stable",
    ...over,
  };
}

function board(players: PublicPlayer[]): PublicBoard {
  return { format: "1qb", tep: false, scoring: "PPR", teams: 12, generated_at: "2026-10-25T00:00:00Z", source_updated_at: "2026-10-25T00:00:00Z", players };
}

describe("slugs", () => {
  it("slugifies names", () => {
    expect(slugify("Ja'Marr Chase")).toBe("jamarr-chase");
    expect(slugify("Amon-Ra St. Brown")).toBe("amon-ra-st-brown");
    expect(slugify("José Ñandú")).toBe("jose-nandu");
    expect(slugify("!!!")).toBe("");
  });

  it("appends the id to every colliding name and maps back", () => {
    const players = [player({ player_id: "1", name: "Mike Williams" }), player({ player_id: "2", name: "Mike Williams" }), player({ player_id: "3", name: "Bijan Robinson" })];
    const slugs = assignSlugs(players);
    expect(slugs.get("1")).toBe("mike-williams-1");
    expect(slugs.get("2")).toBe("mike-williams-2");
    expect(slugs.get("3")).toBe("bijan-robinson");
    expect(findPlayerBySlug(players, "mike-williams-2")?.player_id).toBe("2");
    expect(findPlayerBySlug(players, "mike-williams")).toBeNull();
    expect(findPlayerBySlug(players, "nobody")).toBeNull();
  });
});

describe("position parsing", () => {
  it("accepts only the four positions", () => {
    expect(parsePosition("QB")).toBe("qb");
    expect(parsePosition("k")).toBeNull();
    expect(parsePosition("")).toBeNull();
  });
});

describe("board parsing", () => {
  it("rejects empty or malformed payloads", () => {
    expect(parseBoard(null)).toBeNull();
    expect(parseBoard({ players: [], source_updated_at: "x" })).toBeNull();
    expect(parseBoard({ players: [{ name: "x" }], source_updated_at: "x" })).toBeNull();
    expect(parseBoard({ players: [player()], source_updated_at: "2026-10-25T00:00:00Z" })?.players).toHaveLength(1);
  });
});

describe("noindex / 404 gating on missing data", () => {
  it("rankings need a minimum number of players", () => {
    const few = Array.from({ length: MIN_RANKINGS_PLAYERS - 1 }, (_, i) => player({ player_id: String(i) }));
    expect(isRankingsIndexable(few)).toBe(false);
    expect(isRankingsIndexable([...few, player({ player_id: "x" })])).toBe(true);
  });

  it("a player outside the top 300 has no page", () => {
    const p = player({ overall_rank: 301 });
    expect(isPageEligible(p)).toBe(false);
    expect(isPlayerPageIndexable(p, board([p]), null)).toBe(false);
  });

  it("a player with too few real facts is not indexable", () => {
    const sparse = player({ age: null, years_exp: null, tier: null, trend: null, status: null, injury_status: null });
    expect(playerFacts(sparse, board([sparse]), null).length).toBeLessThan(4);
    expect(isPlayerPageIndexable(sparse, board([sparse]), null)).toBe(false);
  });

  it("a player with no score or an unsupported position is not indexable", () => {
    expect(isPlayerPageIndexable(player({ score: 0 }), board([player({ score: 0 })]), null)).toBe(false);
    expect(isPlayerPageIndexable(player({ position: "K" }), board([player({ position: "K" })]), null)).toBe(false);
  });

  it("a complete player is indexable", () => {
    const p = player();
    expect(isPlayerPageIndexable(p, board([p]), null)).toBe(true);
  });
});

describe("player facts only use provided fields", () => {
  it("omits unknown trend labels, missing injury and null team", () => {
    const p = player({ trend: "Mystery", team: null, injury_status: null });
    const text = playerFacts(p, board([p]), null).join(" ");
    expect(trendLabel("Mystery")).toBeNull();
    expect(text).not.toMatch(/workload trend/);
    expect(text).not.toMatch(/injury/i);
    expect(text).not.toMatch(/for the/);
    expect(text).toContain("#2 among wide receivers");
  });

  it("includes injury, trend and superflex when present", () => {
    const p = player({ injury_status: "Questionable", trend: "Rising" });
    const sf = player({ score: 8500, position_rank: 1, overall_rank: 3 });
    const text = playerFacts(p, board([p]), sf).join(" ");
    expect(text).toContain("Questionable");
    expect(text).toContain("reads rising");
    expect(text).toContain("Superflex his value is 8,500");
  });

  it("finds same-position neighbours", () => {
    const a = player({ player_id: "a", position_rank: 1 });
    const b = player({ player_id: "b", position_rank: 2 });
    const c = player({ player_id: "c", position_rank: 3 });
    const n = neighbors(b, board([c, a, b]));
    expect(n.above?.player_id).toBe("a");
    expect(n.below?.player_id).toBe("c");
  });
});

describe("json-ld", () => {
  it("builds a breadcrumb list with absolute urls and escapes '<'", () => {
    const ld = breadcrumbLd([{ name: "A", path: "/a" }]);
    expect(ld.itemListElement[0].item).toBe("https://app.fantasygmlab.com/a");
    expect(serializeLd({ x: "</script>" })).not.toContain("</script>");
  });
});
