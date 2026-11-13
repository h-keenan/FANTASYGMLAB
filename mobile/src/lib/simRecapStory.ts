// Twin file: web-next/src/lib/simRecapStory.ts and mobile/src/lib/simRecapStory.ts stay identical.
//
// Which pages the weekly-recap story shows and what goes on each one: pure selection logic, no React.
// Every page is glanceable by construction: a hero number plus at most STORY_ITEMS supporting items.
import type { SimRecapScore, SimRecapStarter, SimWeekRecap } from "./simGame";

export const STORY_ITEMS = 3;

export type SimRecapPageKey = "result" | "matchup" | "injuries" | "league" | "next";

export interface SimRecapFacts {
  youId?: string | null;
  /** Names by team id (the recap's standings rows carry them). */
  names: Record<string, string>;
  /** Lineup warnings for the NEXT week (bye/out starters, empty slots) from the game header. */
  lineupWarnings: number;
  /** AI offers waiting in the inbox. */
  offers: number;
  /** The next week's opponent and projection, when the game header has them. */
  nextOpponent?: string | null;
  nextProjection?: { yours: number; theirs: number } | null;
  tradeDeadlineWeek?: number | null;
  /** The week the game is on now (the recap's next week). */
  week?: number | null;
}

const fmt = (n: number) => (Math.round(n * 10) / 10).toFixed(1);

/** The page order: Result, Matchup, Injuries and lineup, Around the league, Next week. Pages with nothing to say are dropped. */
export function simRecapPageKeys(recap: SimWeekRecap, facts: SimRecapFacts): SimRecapPageKey[] {
  const keys: SimRecapPageKey[] = ["result"];
  if (recap.your_game && recap.your_game.starters.length > 0) keys.push("matchup");
  const hurt = (recap.injuries ?? []).length > 0;
  const flagged = (recap.your_game?.starters ?? []).some((s) => s.flag != null);
  if (hurt || flagged || facts.lineupWarnings > 0) keys.push("injuries");
  if (recap.scores.length > 0) keys.push("league");
  if (!recap.season_complete && recap.next_week != null) keys.push("next");
  return keys;
}

export interface SimRecapResultModel {
  kind: "game" | "bye";
  result: string;
  opponent: string;
  yours: number;
  theirs: number;
  /** "Won by 18.7", "Lost by 4.2", "Tied". */
  margin: string;
  best: { name: string; pts: number } | null;
  worst: { name: string; pts: number } | null;
}

export function simRecapResultModel(recap: SimWeekRecap): SimRecapResultModel {
  const g = recap.your_game;
  if (!g) return { kind: "bye", result: "bye", opponent: "", yours: 0, theirs: 0, margin: "Bye week", best: null, worst: null };
  const diff = Math.round((g.your_pts - g.opp_pts) * 10) / 10;
  const margin = diff === 0 ? "Tied" : diff > 0 ? `Won by ${fmt(diff)}` : `Lost by ${fmt(-diff)}`;
  const played = g.starters.filter((s) => s.player && s.flag == null);
  const sorted = [...played].sort((a, b) => b.pts - a.pts);
  const best = recap.mvp ? { name: recap.mvp.player.name, pts: recap.mvp.pts } : sorted[0]?.player ? { name: sorted[0].player.name, pts: sorted[0].pts } : null;
  const last = sorted[sorted.length - 1];
  const worst = recap.bust ? { name: recap.bust.player.name, pts: recap.bust.pts } : last?.player ? { name: last.player.name, pts: last.pts } : null;
  return { kind: "game", result: g.result, opponent: g.opponent_name, yours: g.your_pts, theirs: g.opp_pts, margin, best, worst };
}

export interface SimPositionTotal {
  pos: string;
  pts: number;
  projected: number;
  count: number;
}

const POS_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF"];

/** Points by the starter's own position (a flex RB counts as an RB), in the usual QB-RB-WR-TE-K order. */
export function simPositionTotals(starters: readonly SimRecapStarter[]): SimPositionTotal[] {
  const map = new Map<string, SimPositionTotal>();
  for (const s of starters) {
    if (!s.player) continue;
    const pos = s.player.pos;
    const row = map.get(pos) ?? { pos, pts: 0, projected: 0, count: 0 };
    row.pts += s.pts;
    row.projected += s.player.projection ?? 0;
    row.count += 1;
    map.set(pos, row);
  }
  return [...map.values()]
    .map((r) => ({ ...r, pts: Math.round(r.pts * 10) / 10, projected: Math.round(r.projected * 10) / 10 }))
    .sort((a, b) => (POS_ORDER.indexOf(a.pos) + 100) % 100 - (POS_ORDER.indexOf(b.pos) + 100) % 100);
}

/** The starters worth a look: the highest scorers, at most STORY_ITEMS. */
export function simTopStarters(starters: readonly SimRecapStarter[], n = STORY_ITEMS): SimRecapStarter[] {
  return starters.filter((s) => s.player).sort((a, b) => b.pts - a.pts).slice(0, n);
}

export interface SimRecapInjuryModel {
  yours: number;
  /** Your hurt players first, then the biggest names elsewhere, at most STORY_ITEMS. */
  items: NonNullable<SimWeekRecap["injuries"]>;
  /** Starters who scored 0 because of a bye or injury. */
  zeroStarters: { name: string; flag: "bye" | "out" }[];
}

export function simRecapInjuryModel(recap: SimWeekRecap): SimRecapInjuryModel {
  const all = recap.injuries ?? [];
  const items = [...all].sort((a, b) => Number(b.is_yours) - Number(a.is_yours) || b.weeks - a.weeks).slice(0, STORY_ITEMS);
  const zeroStarters = (recap.your_game?.starters ?? []).filter((s) => s.player && s.flag).map((s) => ({ name: s.player!.name, flag: s.flag as "bye" | "out" }));
  return { yours: all.filter((i) => i.is_yours).length, items, zeroStarters };
}

export interface SimLeagueHighlight {
  key: "top" | "closest" | "blowout" | "trade" | "claim";
  label: string;
  detail: string;
  /** For the hero: the number and who scored it. */
  value?: string;
  who?: string;
}

/** Around the league: the hero is the league's top score; the items are the closest game, the biggest blowout and one move. */
export function simLeagueHighlights(recap: SimWeekRecap, names: Record<string, string>): { hero: SimLeagueHighlight | null; items: SimLeagueHighlight[] } {
  const name = (id: string) => names[id] ?? "A team";
  const played = recap.scores.filter((g): g is SimRecapScore & { home_pts: number; away_pts: number } => g.home_pts != null && g.away_pts != null);
  if (played.length === 0) return { hero: null, items: [] };
  let top = { id: played[0].home, pts: played[0].home_pts };
  for (const g of played) {
    if (g.home_pts > top.pts) top = { id: g.home, pts: g.home_pts };
    if (g.away_pts > top.pts) top = { id: g.away, pts: g.away_pts };
  }
  const hero: SimLeagueHighlight = { key: "top", label: "Top score", detail: `${name(top.id)} ${fmt(top.pts)}`, value: fmt(top.pts), who: name(top.id) };
  const margin = (g: (typeof played)[number]) => Math.abs(g.home_pts - g.away_pts);
  const closest = [...played].sort((a, b) => margin(a) - margin(b))[0];
  const blowout = [...played].sort((a, b) => margin(b) - margin(a))[0];
  const winnerOf = (g: (typeof played)[number]) => (g.home_pts >= g.away_pts ? g.home : g.away);
  const loserOf = (g: (typeof played)[number]) => (g.home_pts >= g.away_pts ? g.away : g.home);
  const items: SimLeagueHighlight[] = [
    { key: "closest", label: "Closest game", detail: `${name(winnerOf(closest))} beat ${name(loserOf(closest))} by ${fmt(margin(closest))}` },
  ];
  if (blowout !== closest) items.push({ key: "blowout", label: "Biggest blowout", detail: `${name(winnerOf(blowout))} beat ${name(loserOf(blowout))} by ${fmt(margin(blowout))}` });
  const trade = (recap.transactions ?? []).find((t) => t.type === "trade" && typeof t.text === "string");
  if (trade && items.length < STORY_ITEMS) items.push({ key: "trade", label: "Trade", detail: String(trade.text) });
  const claim = (recap.waivers ?? []).find((w) => w.ok);
  if (claim && items.length < STORY_ITEMS) items.push({ key: "claim", label: "Waiver claim", detail: `${claim.name} added ${claim.add.name}` });
  return { hero, items: items.slice(0, STORY_ITEMS) };
}

export interface SimNextWeekModel {
  week: number | null;
  opponent: string | null;
  yours: number | null;
  theirs: number | null;
  edge: string | null;
  notes: { label: string; text: string }[];
}

/** Next week: the opponent and projections, then what needs attention (at most STORY_ITEMS notes). */
export function simNextWeekModel(recap: SimWeekRecap, facts: SimRecapFacts): SimNextWeekModel {
  const p = facts.nextProjection ?? null;
  const notes: { label: string; text: string }[] = [];
  if (facts.lineupWarnings > 0) notes.push({ label: "Lineup", text: `${facts.lineupWarnings} issue${facts.lineupWarnings === 1 ? "" : "s"} to fix` });
  if (facts.offers > 0) notes.push({ label: "Offers", text: `${facts.offers} waiting, they expire when you advance` });
  const week = recap.next_week ?? facts.week ?? null;
  if (facts.tradeDeadlineWeek != null && week != null && week <= facts.tradeDeadlineWeek) {
    const left = facts.tradeDeadlineWeek - week;
    notes.push({ label: "Deadline", text: left === 0 ? "Last week to trade" : `Trade deadline in ${left} week${left === 1 ? "" : "s"}` });
  }
  let edge: string | null = null;
  if (p) {
    const d = Math.round((p.yours - p.theirs) * 10) / 10;
    edge = d === 0 ? "Even matchup" : d > 0 ? `You are favored by ${fmt(d)}` : `You are the underdog by ${fmt(-d)}`;
  }
  return { week, opponent: facts.nextOpponent ?? null, yours: p?.yours ?? null, theirs: p?.theirs ?? null, edge, notes: notes.slice(0, STORY_ITEMS) };
}
