// Twin file: web-next/src/lib/simRecapStory.ts and mobile/src/lib/simRecapStory.ts stay identical.
//
// Which pages the weekly-recap story shows and what goes on each one: pure selection logic, no React.
// Every page is glanceable by construction: a hero number plus at most STORY_ITEMS supporting items.
import type { SimGamePlayer, SimRecapScore, SimRecapStarter, SimWeekRecap } from "./simGame";

export const STORY_ITEMS = 3;

export type SimRecapPageKey = "result" | "achievements" | "matchup" | "injuries" | "league" | "standings" | "season" | "next";

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
  /** Playoff spots (settings.playoff_teams): where the standings page draws the cut line. */
  playoffTeams?: number | null;
  /** The week the game is on now (the recap's next week). */
  week?: number | null;
}

const fmt = (n: number) => (Math.round(n * 10) / 10).toFixed(1);

/** The page order: Result, Achievements (only when the week unlocked a badge or hit a milestone), Matchup, Injuries and lineup, Around the league, Standings (regular season), Season (the final week only), Next week. Pages with nothing to say are dropped. */
export function simRecapPageKeys(recap: SimWeekRecap, facts: SimRecapFacts): SimRecapPageKey[] {
  const keys: SimRecapPageKey[] = ["result"];
  // (inline, not imported: the app runs these libs under node:test, which needs no runtime import between twins)
  if (recap.achievements && (recap.achievements.new.length > 0 || recap.achievements.milestones.length > 0)) keys.push("achievements");
  if (recap.your_game && recap.your_game.result !== "bye" && recap.your_game.starters.length > 0) keys.push("matchup");
  const hurt = (recap.injuries ?? []).length > 0;
  const flagged = (recap.your_game?.starters ?? []).some((s) => s.flag != null);
  if (hurt || flagged || facts.lineupWarnings > 0) keys.push("injuries");
  if (recap.scores.length > 0) keys.push("league");
  if (recap.kind === "regular" && (recap.standings ?? []).length > 0) keys.push("standings");
  if (recap.season_complete) keys.push("season");
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
  best: { name: string; pts: number; player: SimGamePlayer | null } | null;
  worst: { name: string; pts: number; player: SimGamePlayer | null } | null;
}

export function simRecapResultModel(recap: SimWeekRecap): SimRecapResultModel {
  const g = recap.your_game;
  // A playoff bye comes from the server as a game whose result is "bye" (no opponent, no scores): never a loss by NaN.
  if (!g || g.result === "bye") return { kind: "bye", result: "bye", opponent: "", yours: 0, theirs: 0, margin: "Bye week", best: null, worst: null };
  const diff = Math.round((g.your_pts - g.opp_pts) * 10) / 10;
  const margin = diff === 0 ? "Tied" : diff > 0 ? `Won by ${fmt(diff)}` : `Lost by ${fmt(-diff)}`;
  const played = g.starters.filter((s) => s.player && s.flag == null);
  const sorted = [...played].sort((a, b) => b.pts - a.pts);
  const best = recap.mvp ? { name: recap.mvp.player.name, pts: recap.mvp.pts, player: recap.mvp.player } : sorted[0]?.player ? { name: sorted[0].player.name, pts: sorted[0].pts, player: sorted[0].player } : null;
  const last = sorted[sorted.length - 1];
  const worst = recap.bust ? { name: recap.bust.player.name, pts: recap.bust.pts, player: recap.bust.player } : last?.player ? { name: last.player.name, pts: last.pts, player: last.player } : null;
  return { kind: "game", result: g.result, opponent: g.opponent_name, yours: g.your_pts, theirs: g.opp_pts, margin, best, worst };
}

export type SimRecapVariant = "win" | "loss" | "tie" | "bye" | "advance" | "eliminated" | "playoff_bye" | "champion" | "runner_up";

export interface SimRecapOutcome {
  variant: SimRecapVariant;
  /** The big word on the result hero: "Victory", "Champions", "Eliminated", "Playoff bye". */
  headline: string;
  /** A short line under it ("You are through to the next round"). */
  sub: string;
  /** Which fixed semantic colour the page glows with. */
  tone: "success" | "danger" | "warning" | "accent" | "premium";
  /** Show the trophy mark (every playoff page, in gold only for the champion). */
  trophy: boolean;
  /** One-shot confetti: the title, and nothing else. */
  celebrate: boolean;
}

/**
 * What the result page is about: a regular-season win/loss/tie/bye, or a playoff round (advance, eliminated, playoff bye) or the
 * championship game (champion crowned, runner-up). Pure: the same recap always gives the same outcome.
 */
export function simRecapOutcome(recap: SimWeekRecap, youId?: string | null): SimRecapOutcome {
  const g = recap.your_game;
  const playoff = recap.kind === "playoff";
  const final = playoff && recap.season_complete;
  const champion = final && recap.champion != null && recap.champion === youId;
  if (champion) return { variant: "champion", headline: "Champions", sub: "You won the title. The trophy is yours.", tone: "premium", trophy: true, celebrate: true };
  if (!g || g.result === "bye") {
    return playoff
      ? { variant: "playoff_bye", headline: "Playoff bye", sub: "You skip this round and wait for the winner.", tone: "accent", trophy: true, celebrate: false }
      : { variant: "bye", headline: "Bye week", sub: "You had a bye this week.", tone: "accent", trophy: false, celebrate: false };
  }
  if (final && g.result === "loss") return { variant: "runner_up", headline: "Runner-up", sub: "So close. You lost the championship game.", tone: "premium", trophy: true, celebrate: false };
  if (playoff && g.result === "loss") return { variant: "eliminated", headline: "Eliminated", sub: "Your title run ends here.", tone: "danger", trophy: true, celebrate: false };
  if (playoff && g.result === "win") return { variant: "advance", headline: "Advancing", sub: "You are through to the next round.", tone: "success", trophy: true, celebrate: false };
  if (g.result === "win") return { variant: "win", headline: "Win", sub: "", tone: "success", trophy: false, celebrate: false };
  if (g.result === "loss") return { variant: "loss", headline: "Loss", sub: "", tone: "danger", trophy: false, celebrate: false };
  return { variant: "tie", headline: "Tie", sub: "", tone: "warning", trophy: false, celebrate: false };
}

export interface SimRecapSeasonModel {
  championName: string | null;
  youChampion: boolean;
  /** "Champions", "Runner-up" or "3rd of 12". */
  finish: string;
  record: string | null;
  items: { key: string; label: string; detail: string }[];
}

const ordinal = (n: number) => {
  const r = n % 100;
  if (r >= 11 && r <= 13) return `${n}th`;
  return `${n}${["th", "st", "nd", "rd"][n % 10 > 3 ? 0 : n % 10]}`;
};

/** The season-complete page: who won it, where you finished, and the awards the standings can back up (at most STORY_ITEMS). */
export function simRecapSeasonModel(recap: SimWeekRecap, facts: SimRecapFacts): SimRecapSeasonModel {
  const rows = recap.standings ?? [];
  const you = rows.find((r) => r.team_id === facts.youId || r.is_you) ?? null;
  const championName = recap.champion ? facts.names[recap.champion] ?? rows.find((r) => r.team_id === recap.champion)?.name ?? null : null;
  const outcome = simRecapOutcome(recap, facts.youId);
  const youChampion = outcome.variant === "champion";
  const finish = youChampion ? "Champions" : outcome.variant === "runner_up" ? "Runner-up" : you ? `${ordinal(you.rank)} of ${rows.length}` : "Season complete";
  const record = you ? `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ""}` : null;
  const items: SimRecapSeasonModel["items"] = [];
  if (championName && !youChampion) items.push({ key: "champion", label: "Champion", detail: championName });
  if (you) items.push({ key: "record", label: "Your record", detail: `${record} · ${fmt(you.pf)} PF` });
  const top = [...rows].sort((a, b) => b.pf - a.pf)[0];
  if (top) items.push({ key: "top", label: "Highest scoring team", detail: `${top.name} · ${fmt(top.pf)} PF${top.is_you ? " (you)" : ""}` });
  if (recap.mvp && items.length < STORY_ITEMS) items.push({ key: "mvp", label: "Final week MVP", detail: `${recap.mvp.player.name} · ${fmt(recap.mvp.pts)}` });
  return { championName, youChampion, finish, record, items: items.slice(0, STORY_ITEMS) };
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

/**
 * The PROJ shown on a recap matchup row: the projection the game displayed going into that week (the server stamps it on the row as
 * `proj`; the row's player brief carries no projection of its own, which is why every row used to read "PROJ -"). Null for a recap saved
 * before the server sent it: shown as "-", never a guess.
 */
export function simRecapProj(s: Pick<SimRecapStarter, "proj">): number | null {
  return typeof s.proj === "number" && Number.isFinite(s.proj) ? s.proj : null;
}

export interface SimRecapInjuryModel {
  yours: number;
  /** Your hurt players first, then the biggest names elsewhere, at most STORY_ITEMS. */
  items: (NonNullable<SimWeekRecap["injuries"]>[number] & { detail: string })[];
  /** Starters who scored 0 because of a bye or injury. */
  zeroStarters: { name: string; flag: "bye" | "out" }[];
}

export function simRecapInjuryModel(recap: SimWeekRecap): SimRecapInjuryModel {
  const all = recap.injuries ?? [];
  // ONE marker per player: the row's chip already says OUT, so the trailing text is only how long ("4 weeks"), never "Out 4w" again.
  const items = [...all]
    .sort((a, b) => Number(b.is_yours) - Number(a.is_yours) || b.weeks - a.weeks)
    .slice(0, STORY_ITEMS)
    .map((i) => ({ ...i, detail: `${i.weeks} ${i.weeks === 1 ? "week" : "weeks"}${i.is_yours ? " · yours" : ""}` }));
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

// ---------------------------------------------------------------------------------------------------------------------
// Page titles: one big bold title per page so you know what you are looking at (shared header, web + app)

export interface SimRecapPageTitle {
  /** The small line above the title ("Week 2 recap"). */
  eyebrow: string;
  /** The big bold title ("Matchup Result"). Never ellipsized: it wraps. */
  title: string;
  /** One line under it when it helps ("You lost by 7.3 to Snap Crackle"); null when the page speaks for itself. */
  subtitle: string | null;
}

/**
 * The header of a recap page. `roundLabel` is the playoff round name for the recap's week ("Quarterfinals", "Semifinals",
 * "Championship"; simPlayoffRoundLabel), used as the result title in the playoffs.
 */
export function simRecapPageTitle(key: SimRecapPageKey, recap: SimWeekRecap, opts: { roundLabel?: string | null; youId?: string | null } = {}): SimRecapPageTitle {
  const playoff = recap.kind === "playoff";
  const eyebrow = `Week ${recap.week} recap`;
  const g = recap.your_game;
  switch (key) {
    case "result": {
      if (!g || g.result === "bye") return { eyebrow, title: playoff ? "Playoff Bye" : "Bye Week", subtitle: playoff ? "You skip this round" : null };
      const diff = Math.round(Math.abs(g.your_pts - g.opp_pts) * 10) / 10;
      const vs = g.opponent_name ? ` ${g.result === "win" ? "over" : "to"} ${g.opponent_name}` : "";
      const subtitle = g.result === "tie" ? `You tied ${g.opponent_name}`.trim() : `You ${g.result === "win" ? "won" : "lost"} by ${fmt(diff)}${vs}`;
      return { eyebrow, title: playoff ? opts.roundLabel || "Playoffs" : "Matchup Result", subtitle };
    }
    case "achievements":
      return { eyebrow, title: "Achievement Unlocked", subtitle: null };
    case "matchup":
      return { eyebrow, title: "How You Scored", subtitle: g && g.optimal_pts != null ? `Best possible lineup: ${fmt(g.optimal_pts)}` : null };
    case "injuries":
      return { eyebrow, title: "Injuries & Lineup", subtitle: null };
    case "league":
      return { eyebrow, title: "Around the League", subtitle: null };
    case "standings":
      return { eyebrow, title: "Standings", subtitle: null };
    case "season":
      return { eyebrow, title: "Season Complete", subtitle: null };
    case "next":
      return { eyebrow, title: "Next Week", subtitle: null };
  }
}

// ---------------------------------------------------------------------------------------------------------------------
// Standings page: the league table with a playoff cut line and how far each team moved since last week

export type SimStandingsStatus = "in" | "bubble" | "out";

export interface SimStandingsRow {
  teamId: string;
  name: string;
  rank: number;
  isYou: boolean;
  record: string;
  pf: number;
  /** Spots moved since the previous week: > 0 up, < 0 down, 0 no change, null when there is no previous week to compare. */
  delta: number | null;
  status: SimStandingsStatus;
  /** Playoff seed (1..playoffTeams) for the teams currently inside the cut; null outside. */
  seed: number | null;
}

export interface SimStandingsModel {
  rows: SimStandingsRow[];
  /** The compact list: top 6, your team and the cut-line neighbours, in rank order. */
  compact: SimStandingsRow[];
  spots: number;
  you: SimStandingsRow | null;
  /** The hero line: "Seed 3, up 2" / "Out of the picture". */
  caption: string;
}

/** "▲2" / "▼1" / "–" text for a movement; empty when unknown. */
export function simMovementText(delta: number | null | undefined): string {
  if (delta == null) return "";
  return delta > 0 ? `\u25B2${delta}` : delta < 0 ? `\u25BC${-delta}` : "\u2013";
}

export function simRecapStandingsModel(recap: SimWeekRecap, facts: Pick<SimRecapFacts, "youId" | "playoffTeams">): SimStandingsModel {
  const src = [...(recap.standings ?? [])].sort((a, b) => a.rank - b.rank);
  const spots = Math.max(0, facts.playoffTeams ?? 0);
  const rows: SimStandingsRow[] = src.map((r) => ({
    teamId: r.team_id,
    name: r.name,
    rank: r.rank,
    isYou: r.is_you || r.team_id === facts.youId,
    record: `${r.wins}-${r.losses}${r.ties ? `-${r.ties}` : ""}`,
    pf: r.pf,
    delta: typeof r.rank_delta === "number" ? r.rank_delta : null,
    status: spots > 0 && r.rank <= spots ? (r.rank === spots ? "bubble" : "in") : spots > 0 && r.rank === spots + 1 ? "bubble" : "out",
    seed: spots > 0 && r.rank <= spots ? r.rank : null,
  }));
  const you = rows.find((r) => r.isYou) ?? null;
  const keep = new Set<string>(rows.slice(0, 6).map((r) => r.teamId));
  if (you) keep.add(you.teamId);
  for (const r of rows) if (spots > 0 && (r.rank === spots || r.rank === spots + 1)) keep.add(r.teamId);
  const compact = rows.filter((r) => keep.has(r.teamId));
  let caption = "";
  if (you) {
    const place = you.seed != null ? `Seed ${you.seed}` : spots > 0 ? "Outside the cut" : `Rank ${you.rank}`;
    const move = you.delta == null ? "" : you.delta > 0 ? `, up ${you.delta}` : you.delta < 0 ? `, down ${-you.delta}` : ", no change";
    caption = `${place}${move}`;
  }
  return { rows, compact, spots, you, caption };
}
