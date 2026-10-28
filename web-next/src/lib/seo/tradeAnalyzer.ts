/**
 * Pure logic for the public, logged-out Trade Analyzer (/trade-analyzer).
 *
 * Everything here runs on the anonymous public value board
 * (GET /v1/public/dynasty-values), the same numbers behind the rankings and
 * trade value chart pages. There is no roster, league or account input, so
 * the verdict is deliberately VALUE-ONLY and labeled as such: it sums each
 * side's value. The in-app Trade Analyzer additionally weighs lineup impact,
 * roster needs, byes/injuries and consolidation, which is the soft gate the
 * page promotes.
 */
import type { PublicBoard, ValueFormat } from "./publicValues";
import { TRADE_ANALYZER_PUBLIC_PATH } from "./site";

export const TRADE_ANALYZER_PATH = TRADE_ANALYZER_PUBLIC_PATH;
export const MAX_ASSETS_PER_SIDE = 8;

/** Index into TradeBoardPlayer.v: [1QB, Superflex, 1QB+TEP, Superflex+TEP]. */
export interface TradeBoardPlayer {
  id: string;
  name: string;
  pos: string;
  team: string | null;
  age: number | null;
  /** Injury designation (Questionable/Out/IR...) or null when healthy. */
  inj: string | null;
  v: [number, number, number, number];
}

export interface TradeBoard {
  updated: string;
  /** False when the TE-premium boards could not be loaded. */
  tepAvailable: boolean;
  players: TradeBoardPlayer[];
}

export interface TradeSettings {
  format: ValueFormat;
  tep: boolean;
}

export function valueIndex(settings: TradeSettings): 0 | 1 | 2 | 3 {
  return ((settings.format === "superflex" ? 1 : 0) + (settings.tep ? 2 : 0)) as 0 | 1 | 2 | 3;
}

export function valueOf(player: TradeBoardPlayer, settings: TradeSettings): number {
  return player.v[valueIndex(settings)] ?? 0;
}

/** Merge the four fetched boards into the compact client payload. Players
 * missing from any board are dropped so every format has a real value. */
export function mergeBoards(boards: {
  std1qb: PublicBoard;
  stdSf: PublicBoard;
  tep1qb: PublicBoard | null;
  tepSf: PublicBoard | null;
}): TradeBoard {
  const tepOk =
    boards.tep1qb !== null && boards.tepSf !== null && boards.tep1qb.tep === true && boards.tepSf.tep === true;
  const byId = (board: PublicBoard | null) => new Map((board?.players ?? []).map((p) => [p.player_id, p]));
  const sf = byId(boards.stdSf);
  const t1 = byId(tepOk ? boards.tep1qb : null);
  const ts = byId(tepOk ? boards.tepSf : null);
  const players: TradeBoardPlayer[] = [];
  for (const p of boards.std1qb.players) {
    const s = sf.get(p.player_id);
    if (!s) continue;
    let a = t1.get(p.player_id);
    let b = ts.get(p.player_id);
    if (tepOk && (!a || !b)) continue;
    if (!tepOk) {
      a = p;
      b = s;
    }
    players.push({
      id: p.player_id,
      name: p.name,
      pos: p.position,
      team: p.team,
      age: p.age,
      inj: p.injury_status && !/^(na|n\/a)$/i.test(p.injury_status) ? p.injury_status : null,
      v: [p.score, s.score, a!.score, b!.score],
    });
  }
  players.sort((x, y) => y.v[0] - x.v[0]);
  return { updated: boards.std1qb.source_updated_at, tepAvailable: tepOk, players };
}

// ---------------------------------------------------------------- search

export function normalizeName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** Autocomplete: every query token must match; word-start beats substring,
 * and value breaks ties so the famous player is first. */
export function searchPlayers(
  players: readonly TradeBoardPlayer[],
  query: string,
  settings: TradeSettings,
  excludeIds: ReadonlySet<string>,
  limit = 8,
): TradeBoardPlayer[] {
  const q = normalizeName(query);
  const pool = players.filter((p) => !excludeIds.has(p.id));
  if (!q) return [...pool].sort((a, b) => valueOf(b, settings) - valueOf(a, settings)).slice(0, limit);
  const tokens = q.split(" ");
  const scored: { p: TradeBoardPlayer; rank: number }[] = [];
  for (const p of pool) {
    const name = normalizeName(p.name);
    if (!tokens.every((t) => name.includes(t))) continue;
    const words = name.split(" ");
    let rank = 2;
    if (name.startsWith(q)) rank = 0;
    else if (tokens.every((t) => words.some((w) => w.startsWith(t)))) rank = 1;
    scored.push({ p, rank });
  }
  scored.sort((x, y) => x.rank - y.rank || valueOf(y.p, settings) - valueOf(x.p, settings));
  return scored.slice(0, limit).map((s) => s.p);
}

// ----------------------------------------------------------- URL state

export interface TradeUrlState {
  a: string[];
  b: string[];
  settings: TradeSettings;
}

const ID_PATTERN = /^[A-Za-z0-9_-]{1,24}$/;

function parseIds(raw: string | null): string[] {
  if (!raw) return [];
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const id = part.trim();
    if (ID_PATTERN.test(id) && !out.includes(id)) out.push(id);
    if (out.length >= MAX_ASSETS_PER_SIDE) break;
  }
  return out;
}

/** ?a=ids&b=ids&f=sf&tep=1. Unknown/malformed input degrades to empty. */
export function parseTradeUrl(search: string): TradeUrlState {
  const params = new URLSearchParams(search);
  const a = parseIds(params.get("a"));
  const b = parseIds(params.get("b")).filter((id) => !a.includes(id));
  const f = (params.get("f") || "").toLowerCase();
  return {
    a,
    b,
    settings: { format: f === "sf" || f === "superflex" ? "superflex" : "1qb", tep: params.get("tep") === "1" },
  };
}

export function buildTradeSearch(state: TradeUrlState): string {
  const params = new URLSearchParams();
  if (state.a.length) params.set("a", state.a.join(","));
  if (state.b.length) params.set("b", state.b.join(","));
  if (state.settings.format === "superflex") params.set("f", "sf");
  if (state.settings.tep) params.set("tep", "1");
  const text = params.toString().replace(/%2C/g, ",");
  return text ? `?${text}` : "";
}

// -------------------------------------------------------------- verdict

export type TradeBand = "empty" | "fair" | "slight" | "clear" | "lopsided";
export type TradeWinner = "a" | "b" | "even";

export interface TradeEvaluation {
  totalA: number;
  totalB: number;
  /** receive (B) minus send (A): positive means you come out ahead on value. */
  diff: number;
  winner: TradeWinner;
  band: TradeBand;
  headline: string;
  detail: string;
  caveats: string[];
  /** Real board player closest in value to the gap, when one side trails. */
  balancer: TradeBoardPlayer | null;
}

export const FAIR_PCT = 0.06;
export const SLIGHT_PCT = 0.15;
export const CLEAR_PCT = 0.3;

export function evaluateTrade(
  sideA: readonly TradeBoardPlayer[],
  sideB: readonly TradeBoardPlayer[],
  settings: TradeSettings,
  board: readonly TradeBoardPlayer[] = [],
): TradeEvaluation {
  const totalA = sideA.reduce((sum, p) => sum + valueOf(p, settings), 0);
  const totalB = sideB.reduce((sum, p) => sum + valueOf(p, settings), 0);
  const diff = totalB - totalA;
  const base: TradeEvaluation = {
    totalA,
    totalB,
    diff,
    winner: "even",
    band: "empty",
    headline: "Add players to both sides",
    detail: "Search for the players you would send and the players you would get back.",
    caveats: [],
    balancer: null,
  };
  if (sideA.length === 0 || sideB.length === 0) return base;

  const larger = Math.max(totalA, totalB);
  const pct = larger > 0 ? Math.abs(diff) / larger : 0;
  const band: TradeBand = pct < FAIR_PCT ? "fair" : pct < SLIGHT_PCT ? "slight" : pct < CLEAR_PCT ? "clear" : "lopsided";
  const winner: TradeWinner = band === "fair" ? "even" : diff > 0 ? "b" : "a";

  let headline: string;
  if (band === "fair") headline = "Fair trade on value";
  else if (winner === "b") {
    headline = band === "slight" ? "Slight edge to you" : band === "clear" ? "You win this trade on value" : "Lopsided in your favor";
  } else {
    headline = band === "slight" ? "Slight edge to them" : band === "clear" ? "You lose this trade on value" : "Lopsided against you";
  }
  const gap = Math.abs(Math.round(diff)).toLocaleString();
  const detail =
    band === "fair"
      ? `Both sides are within ${Math.round(FAIR_PCT * 100)}% of each other (${Math.round(totalA).toLocaleString()} vs ${Math.round(totalB).toLocaleString()}).`
      : `${winner === "b" ? "You get" : "They get"} ${gap} more value than ${winner === "b" ? "you send" : "they send"} (${Math.round(totalA).toLocaleString()} sent vs ${Math.round(totalB).toLocaleString()} received).`;

  const caveats: string[] = [];
  if (sideA.length !== sideB.length) {
    const many = sideA.length > sideB.length ? "You send" : "You get";
    caveats.push(
      `${many} more players than the other side. Value totals add up, but consolidating into one better player is worth more than the same total spread across depth, and only the app knows if you have a roster spot for them.`,
    );
  }
  const hurt = [...sideA, ...sideB].filter((p) => p.inj);
  if (hurt.length) {
    caveats.push(
      `${hurt.map((p) => `${p.name} (${p.inj})`).join(", ")} ${hurt.length === 1 ? "has" : "have"} an injury designation. Values here do not discount for missed weeks.`,
    );
  }

  let balancer: TradeBoardPlayer | null = null;
  if (band !== "fair") {
    const used = new Set([...sideA, ...sideB].map((p) => p.id));
    const target = Math.abs(diff);
    let best = Infinity;
    for (const p of board) {
      if (used.has(p.id)) continue;
      const delta = Math.abs(valueOf(p, settings) - target);
      if (delta < best) {
        best = delta;
        balancer = p;
      }
    }
    if (balancer && best > target * 0.25) balancer = null;
  }

  return { totalA, totalB, diff, winner, band, headline, detail, caveats, balancer };
}

// ------------------------------------------------------------------ CTAs

export type TradeCta = "verdict" | "roster_impact" | "partner_fit" | "counter_offers" | "sample";

/** Internal CTA links carry first-touch-safe utm tokens (lib/attribution.ts:
 * [a-z0-9_.-]); an earlier external first touch is never overwritten. */
export function ctaHref(cta: TradeCta): string {
  const base = cta === "sample" ? "/sample-league" : "/";
  const params = new URLSearchParams({
    utm_source: "seo_trade_analyzer",
    utm_medium: "organic_cta",
    utm_campaign: `public_trade_analyzer_${cta}`,
  });
  return `${base}?${params.toString()}`;
}

// ------------------------------------------------------------------- FAQ

export const TRADE_FAQ: readonly { q: string; a: string }[] = [
  {
    q: "How does this fantasy football trade analyzer work?",
    a: "Search for the players you would send and the players you would get, add them to each side, and the tool totals each side's FantasyDesk dynasty value and tells you whether the trade is fair or which side wins. Values update daily and are the same numbers used in our rankings and trade value chart.",
  },
  {
    q: "Is it for dynasty or redraft leagues?",
    a: "The values are dynasty values (long-term player value including age and role) for a default 12-team PPR league. Switch between 1QB and Superflex, and turn on tight end premium, to match your league. Redraft-only leagues should treat it as a rough guide.",
  },
  {
    q: "Why is the verdict value-only?",
    a: "A public tool cannot see your roster. It cannot tell that a trade leaves you without a startable running back this week, or that you already have three tight ends. The FantasyDesk app does: connect your Sleeper league for a roster-aware verdict that checks your starting lineup, byes and injuries, your team's needs, the partner's fit and counter-offers.",
  },
  {
    q: "Does it include draft picks?",
    a: "Not on this page. Pick values depend on your league (how many teams, who owns the picks and where they project), so pick-inclusive trades are evaluated inside the app with your league's real picks.",
  },
  {
    q: "Where do the player values come from?",
    a: "FantasyDesk blends market trade values with age, production and role into one dynasty value per player. See How we value players for the full methodology; values are informed by FantasyCalc market data.",
  },
  {
    q: "Is the trade analyzer free?",
    a: "Yes. The value-only trade analyzer is free and needs no account. A free account unlocks the roster-aware verdict for your own Sleeper league.",
  },
];
