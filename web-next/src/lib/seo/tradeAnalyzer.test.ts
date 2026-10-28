import { describe, expect, it } from "vitest";

import type { PublicBoard, PublicPlayer } from "./publicValues";
import {
  buildTradeSearch,
  ctaHref,
  evaluateTrade,
  mergeBoards,
  normalizeName,
  parseTradeUrl,
  searchPlayers,
  TRADE_FAQ,
  valueOf,
  type TradeBoardPlayer,
  type TradeSettings,
} from "./tradeAnalyzer";
import { bandForScore, TRADE_VALUE_GOLDEN } from "../tradeValueBands.generated";
import { faqLd } from "./jsonld";
import { parseAttribution } from "../attribution";

const STD: TradeSettings = { format: "1qb", tep: false };
const SF: TradeSettings = { format: "superflex", tep: false };
const TEP: TradeSettings = { format: "1qb", tep: true };

function p(id: string, name: string, pos: string, v1: number, over: Partial<TradeBoardPlayer> = {}): TradeBoardPlayer {
  return { id, name, pos, team: "KC", age: 25, inj: null, v: [v1, v1 + 500, v1 + (pos === "TE" ? 400 : 0), v1 + 500 + (pos === "TE" ? 400 : 0)], ...over };
}

const BOARD = [
  p("1", "Ja'Marr Chase", "WR", 9000),
  p("2", "Josh Allen", "QB", 7000),
  p("3", "Brock Bowers", "TE", 6500),
  p("4", "Bijan Robinson", "RB", 8800),
  p("5", "Josh Jacobs", "RB", 4000),
  p("6", "Amon-Ra St. Brown", "WR", 6000),
  p("7", "Tank Dell", "WR", 2500),
];

describe("search", () => {
  it("normalizes accents and punctuation", () => {
    expect(normalizeName("Ja'Marr  Chase")).toBe("ja marr chase");
    expect(normalizeName("Amon-Ra St. Brown")).toBe("amon ra st brown");
  });

  it("matches every token, prefers prefix/word-start, breaks ties by value", () => {
    const hits = searchPlayers(BOARD, "josh", STD, new Set());
    expect(hits.map((h) => h.name)).toEqual(["Josh Allen", "Josh Jacobs"]);
    expect(searchPlayers(BOARD, "jamarr", STD, new Set())).toEqual([]);
    expect(searchPlayers(BOARD, "ja marr", STD, new Set())[0].name).toBe("Ja'Marr Chase");
    expect(searchPlayers(BOARD, "brown amon", STD, new Set())[0].name).toBe("Amon-Ra St. Brown");
  });

  it("excludes already-added players and lists top values for an empty query", () => {
    expect(searchPlayers(BOARD, "", STD, new Set(["1"]), 2).map((x) => x.id)).toEqual(["4", "2"]);
  });
});

describe("evaluateTrade", () => {
  it("is empty until both sides have players", () => {
    expect(evaluateTrade([BOARD[0]], [], STD).band).toBe("empty");
  });

  it("calls near-equal totals fair", () => {
    const e = evaluateTrade([p("20", "Even A", "WR", 5000)], [p("21", "Even B", "WR", 5100)], STD, BOARD);
    expect(e.band).toBe("fair");
    expect(e.badge).toBe("Fair");
    expect(e.winner).toBe("even");
    expect(e.balancer).toBeNull();
  });

  it("scores the receive side as the user's win and the send side as a loss", () => {
    const win = evaluateTrade([BOARD[4]], [BOARD[0]], STD, BOARD);
    expect(win.winner).toBe("b");
    expect(win.diff).toBe(5000);
    expect(win.band).toBe("lopsided");
    expect(win.headline).toMatch(/favor/);
    const loss = evaluateTrade([BOARD[0]], [BOARD[4]], STD, BOARD);
    expect(loss.winner).toBe("a");
    expect(loss.diff).toBe(-5000);
    expect(loss.headline).toMatch(/against you/);
  });

  it("suggests the real board player closest to the gap, never one already in the deal", () => {
    // gap 2000 (6000 vs 4000): closest unused is Tank Dell 2500
    const e = evaluateTrade([BOARD[4]], [BOARD[5]], STD, BOARD);
    expect(e.band).toBe("lopsided"); // -2000: a "decline" on the shared ladder
    expect(e.balancer?.id).toBe("7");
    // no suggestion when nothing on the board is within 25% of the gap
    expect(evaluateTrade([BOARD[4]], [BOARD[5]], STD, [p("9", "Far", "WR", 90000)]).balancer).toBeNull();
  });

  it("flags uneven player counts and injury designations, without discounting values", () => {
    const hurt = p("8", "Hurt Guy", "RB", 3000, { inj: "Questionable" });
    const e = evaluateTrade([BOARD[4], hurt], [BOARD[5]], STD);
    expect(e.caveats.join(" ")).toMatch(/more players/);
    expect(e.caveats.join(" ")).toMatch(/Hurt Guy \(Questionable\)/);
    expect(e.totalA).toBe(7000);
  });

  it("uses the selected format and TE premium values", () => {
    const te = BOARD[2];
    expect(valueOf(te, STD)).toBe(6500);
    expect(valueOf(te, SF)).toBe(7000);
    expect(valueOf(te, TEP)).toBe(6900);
  });
});

describe("public verdict uses the shared band ladder (audit C1/C2)", () => {
  it("every golden score lands in the same band, badge and tone the in-app verdict uses", () => {
    for (const { score, id } of TRADE_VALUE_GOLDEN) {
      const e = evaluateTrade([p("a", "A", "WR", 20000)], [p("b", "B", "WR", 20000 + score)], STD);
      expect(e.badge, String(score)).toBe(bandForScore(score).badge);
      expect(e.diff).toBe(score);
      expect(e.winner).toBe(id === "even" ? "even" : score > 0 ? "b" : "a");
    }
  });

  it("prices trades with trade_score (the age-curved value), not the rankings score", () => {
    const player = (id: string, score: number, trade_score?: number) => ({
      player_id: id, name: id, position: "WR", team: "KC", age: 30, years_exp: 8, status: null, injury_status: null,
      score, trade_score, overall_rank: 1, position_rank: 1, tier: null, overall_rating: null, trend: null,
    });
    const board = (s: number, t?: number): PublicBoard => ({
      format: "1qb", tep: false, scoring: "PPR", teams: 12, generated_at: "", source_updated_at: "2026-10-27", players: [player("x", s, t)],
    });
    const merged = mergeBoards({ std1qb: board(9000, 8000), stdSf: board(9000, 8000), tep1qb: null, tepSf: null });
    expect(merged.players[0].v[0]).toBe(8000);
    const legacy = mergeBoards({ std1qb: board(9000), stdSf: board(9000), tep1qb: null, tepSf: null });
    expect(legacy.players[0].v[0]).toBe(9000);
  });
});

describe("shareable URL state", () => {
  it("round-trips sides and settings", () => {
    const state = { a: ["1", "2"], b: ["3"], settings: { format: "superflex", tep: true } as TradeSettings };
    const search = buildTradeSearch(state);
    expect(search).toBe("?a=1,2&b=3&f=sf&tep=1");
    expect(parseTradeUrl(search)).toEqual(state);
  });

  it("is empty for the default state and tolerates junk, dupes and overflow", () => {
    expect(buildTradeSearch({ a: [], b: [], settings: STD })).toBe("");
    const parsed = parseTradeUrl("?a=1,1,<script>,2,../x&b=2,3&f=wat&tep=yes");
    expect(parsed.a).toEqual(["1", "2"]);
    expect(parsed.b).toEqual(["3"]); // already on side A
    expect(parsed.settings).toEqual({ format: "1qb", tep: false });
    expect(parseTradeUrl(`?a=${Array.from({ length: 20 }, (_, i) => i + 1).join(",")}`).a).toHaveLength(8);
  });
});

describe("mergeBoards", () => {
  function pub(id: string, score: number, over: Partial<PublicPlayer> = {}): PublicPlayer {
    return { player_id: id, name: `P${id}`, position: "WR", team: "KC", age: 25, years_exp: 3, status: "Active", injury_status: null, score, overall_rank: 1, position_rank: 1, tier: null, overall_rating: null, trend: null, ...over };
  }
  function board(players: PublicPlayer[], over: Partial<PublicBoard> = {}): PublicBoard {
    return { format: "1qb", tep: false, scoring: "PPR", teams: 12, generated_at: "x", source_updated_at: "2026-10-27T00:00:00Z", players, ...over };
  }

  it("merges the four boards by player id and drops players missing from any", () => {
    const merged = mergeBoards({
      std1qb: board([pub("1", 100), pub("2", 90, { injury_status: "NA" }), pub("3", 80)]),
      stdSf: board([pub("1", 150), pub("2", 95)]),
      tep1qb: board([pub("1", 100), pub("2", 90)], { tep: true }),
      tepSf: board([pub("1", 150), pub("2", 95)], { tep: true }),
    });
    expect(merged.tepAvailable).toBe(true);
    expect(merged.players.map((x) => x.id)).toEqual(["1", "2"]);
    expect(merged.players[0].v).toEqual([100, 150, 100, 150]);
    expect(merged.players[1].inj).toBeNull(); // Sleeper's "NA" is not an injury
  });

  it("reports TEP unavailable when the API ignores the flag (old backend)", () => {
    const merged = mergeBoards({
      std1qb: board([pub("1", 100)]),
      stdSf: board([pub("1", 150)]),
      tep1qb: board([pub("1", 100)]), // tep:false echoed back
      tepSf: board([pub("1", 150)]),
    });
    expect(merged.tepAvailable).toBe(false);
    expect(merged.players[0].v).toEqual([100, 150, 100, 150]);
  });
});

describe("SEO + attribution contract", () => {
  it("CTA links carry attribution tokens the first-touch parser accepts", () => {
    const href = ctaHref("verdict");
    expect(href.startsWith("/?")).toBe(true);
    const parsed = parseAttribution(href.slice(1), "", "app.fantasygmlab.com");
    expect(parsed.utm_source).toBe("seo_trade_analyzer");
    expect(parsed.utm_medium).toBe("organic_cta");
    expect(parsed.utm_campaign).toBe("public_trade_analyzer_verdict");
    expect(ctaHref("sample").startsWith("/sample-league?")).toBe(true);
  });

  it("FAQ JSON-LD mirrors the visible FAQ", () => {
    const ld = faqLd(TRADE_FAQ) as { "@type": string; mainEntity: { name: string; acceptedAnswer: { text: string } }[] };
    expect(ld["@type"]).toBe("FAQPage");
    expect(ld.mainEntity).toHaveLength(TRADE_FAQ.length);
    expect(ld.mainEntity[0].name).toBe(TRADE_FAQ[0].q);
    expect(TRADE_FAQ.every((f) => f.q && f.a.length > 40)).toBe(true);
  });
});
