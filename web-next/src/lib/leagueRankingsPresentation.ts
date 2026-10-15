import type { TeamRanking } from "./api";

/**
 * League Rankings presentation helpers — pure ports of small, PURE
 * formatting/labeling functions from modules/league_workspace_ui.py (the
 * real Streamlit "League Rankings" page's own rendering module). No
 * valuation, ranking, or scoring logic lives here — every rank/score this
 * page shows is already computed server-side by modules.league_rankings
 * and exposed as-is via GET .../team-rankings; this file only decides how
 * to format/color/caption an already-final value, the same tier of port
 * matchupPresentation.ts/waiversPresentation.ts already are for their pages.
 */

/** "#4" for a rank unique to one team, "T4" when 2+ teams share that exact
 * dense rank — byte-for-byte port of league_workspace_ui._format_rank. */
export function formatRank(value: number | null | undefined, tied = false): string {
  if (value == null || !Number.isFinite(value) || value <= 0) return "N/A";
  return `${tied ? "T" : "#"}${Math.round(value)}`;
}

/** Best team in a group -> 100, worst -> 0 — port of
 * league_workspace_ui._percentile_from_rank (same transform mobile's
 * percentileFromRank uses). */
export function percentileFromRank(rank: number | null | undefined, totalTeams: number): number | null {
  if (rank == null || rank <= 0 || totalTeams <= 1) return null;
  return ((totalTeams - rank) / (totalTeams - 1)) * 100;
}

/** Red/gold/green percentile banding, same thresholds as
 * league_workspace_ui._metric_tone_band, mapped onto this app's existing
 * --value-ring--low/mid/high color tokens (globals.css) rather than
 * inventing a new tone vocabulary for this page. */
export function metricToneColor(percentile: number | null): string {
  if (percentile === null) return "var(--color-text-primary)";
  if (percentile < 34) return "var(--color-danger)";
  if (percentile < 67) return "var(--color-action)";
  return "var(--color-success)";
}

/** Rounds to the nearest whole number with thousands separators — port of
 * league_workspace_ui._format_score. */
export function formatScore(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "0";
  return Math.round(value).toLocaleString();
}

export type RankBoardKey = "power" | "franchise" | "draft_capital" | "starter" | "bench";

/** Which other ranks to show as a board row's secondary context line —
 * byte-for-byte port of league_workspace_ui._board_secondary_parts
 * (deliberately omits the board's own primary rank from its own
 * secondary line). */
export function boardSecondaryParts(board: RankBoardKey, team: TeamRanking): string[] {
  const power = formatRank(team.power_rank, team.power_rank_tied);
  const franchise = formatRank(team.franchise_rank, team.franchise_rank_tied);
  const draft = formatRank(team.draft_capital_rank, team.draft_capital_rank_tied);
  const starter = formatRank(team.starter_rank, team.starter_rank_tied);
  const bench = formatRank(team.bench_rank, team.bench_rank_tied);

  if (board === "power") {
    return [`Franchise ${franchise}`, `Draft ${draft}`, `Starter ${starter}`];
  }
  if (board === "franchise") {
    return [`Roster Power ${power}`, `Draft ${draft}`, `Starter ${starter}`];
  }
  if (board === "draft_capital") {
    const firsts = team.first_rounders ?? 0;
    return [
      `Roster Power ${power}`,
      `Franchise ${franchise}`,
      firsts ? `${firsts} firsts` : `Picks ${team.pick_count ?? 0}`,
    ];
  }
  // starter / bench
  return [`Roster Power ${power}`, `Franchise ${franchise}`, `Starter ${starter}`, `Bench ${bench}`, `Draft ${draft}`];
}

export const RANK_BOARD_CONFIG: Record<
  RankBoardKey,
  { title: string; kicker: string; note: string; scoreLabel: string; rankField: keyof TeamRanking; tiedField: keyof TeamRanking; scoreField: keyof TeamRanking }
> = {
  power: {
    title: "Roster Power Rankings",
    kicker: "Who is strongest",
    note: "Who is best equipped to win games right now — not who has the best record.",
    scoreLabel: "Starter-Weighted Score",
    rankField: "power_rank",
    tiedField: "power_rank_tied",
    scoreField: "power_score",
  },
  franchise: {
    title: "Franchise Value",
    kicker: "Dynasty value",
    note: "Total roster value plus owned draft capital — the long-term asset base.",
    scoreLabel: "Roster Value + Draft Capital",
    rankField: "franchise_rank",
    tiedField: "franchise_rank_tied",
    scoreField: "franchise_score",
  },
  draft_capital: {
    title: "Draft Capital",
    kicker: "Future capital",
    note: "Who controls upcoming picks. Open Draft Center for pick-by-pick ownership.",
    scoreLabel: "Draft Capital Score",
    rankField: "draft_capital_rank",
    tiedField: "draft_capital_rank_tied",
    scoreField: "draft_capital_score",
  },
  starter: {
    title: "Starter Quality",
    kicker: "Who starts best",
    note: "Combined strength of each team's starting lineup only — bench excluded.",
    scoreLabel: "Starter Score",
    rankField: "starter_rank",
    tiedField: "starter_rank_tied",
    scoreField: "starter_score",
  },
  bench: {
    title: "Bench Depth",
    kicker: "Who's deepest",
    note: "Depth and value of each team's bench — usable reinforcements if a starter goes down.",
    scoreLabel: "Bench Score",
    rankField: "bench_rank",
    tiedField: "bench_rank_tied",
    scoreField: "bench_score",
  },
};

/** Sort a copy of `teams` by the given board's rank (ascending), tie-broken
 * by score descending — same ordering league_workspace_ui.
 * render_power_rankings_board applies before rendering each board. A pure
 * presentation sort of already-computed rank/score fields, not a
 * recomputation of either. */
export function sortByBoard(teams: TeamRanking[], board: RankBoardKey): TeamRanking[] {
  const config = RANK_BOARD_CONFIG[board];
  return [...teams].sort((a, b) => {
    const rankA = (a[config.rankField] as number | null) ?? Number.MAX_SAFE_INTEGER;
    const rankB = (b[config.rankField] as number | null) ?? Number.MAX_SAFE_INTEGER;
    if (rankA !== rankB) return rankA - rankB;
    const scoreA = (a[config.scoreField] as number | null) ?? 0;
    const scoreB = (b[config.scoreField] as number | null) ?? 0;
    return scoreB - scoreA;
  });
}

/** Sort a copy of `teams` by the already-computed Standings rank — a pure
 * presentation sort (the tie-break math itself lives server-side in
 * modules.league_standings.build_league_standings_bundle; `standing_rank`
 * is already final). */
export function sortByStanding(teams: TeamRanking[]): TeamRanking[] {
  return [...teams].sort((a, b) => {
    const rankA = a.standing_rank ?? Number.MAX_SAFE_INTEGER;
    const rankB = b.standing_rank ?? Number.MAX_SAFE_INTEGER;
    return rankA - rankB;
  });
}

/** Honest, not-ready-yet copy per real `reason` code from GET
 * .../team-rankings (modules.rankings' own gate), matching this app's
 * other pages' reason-message convention. */
export function teamRankingsReasonMessage(reason: string): string {
  if (reason === "no_player_data") {
    return "Player data isn't available right now — try again in a bit.";
  }
  if (reason === "no_rankings_data") {
    return "We don't have enough roster data to build League Rankings for this league yet.";
  }
  return "League Rankings aren't available for this league right now.";
}

/** Byte-for-byte the same copy mobile's PlayoffOddsScreen.tsx
 * REASON_MESSAGES uses for GET .../playoff-odds' `reason` field (see
 * modules.playoff_simulator.build_league_playoff_odds). */
export const PLAYOFF_ODDS_REASON_MESSAGES: Record<string, string> = {
  offseason: "Playoff odds will be available once the regular season begins.",
  no_playoff_format:
    "This league's playoff format isn't set yet — odds need a real playoff-team count from league settings.",
  no_rankings_data: "We don't have enough roster data to compute Roster Power for this league yet.",
  unavailable: "Playoff odds aren't available for this league right now.",
};

export function playoffOddsReasonMessage(reason: string): string {
  return PLAYOFF_ODDS_REASON_MESSAGES[reason] ?? "Playoff odds aren't available for this league right now.";
}

/** Zero, one, or several real, data-backed team signals (Highly Active /
 * Quiet Manager, Pick Hoarder / Pick Seller, Veteran Collector / Youth
 * Builder, Hot Streak / Cold Streak, Top-Heavy Roster) — same tone mapping
 * mobile's TeamsScreen.tsx TEAM_BADGE_VISUALS uses, collapsed to the
 * success/warning/muted tone vocabulary this page already has on hand
 * instead of introducing a fourth color family just for this list. */
export function teamBadgeTone(label: string): "positive" | "negative" | "neutral" {
  if (label === "Hot Streak") return "positive";
  if (label === "Cold Streak" || label === "Top-Heavy Roster") return "negative";
  return "neutral";
}
