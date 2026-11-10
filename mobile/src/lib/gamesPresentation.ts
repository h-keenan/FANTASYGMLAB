/**
 * Games (Season Simulator + Pick'em) presentation helpers. Pure; mirrors
 * web-next/src/lib/gamesPresentation.ts. Every string answers a real `reason`
 * code from modules/games.py or modules/playoff_simulator.py.
 */

export const GAMES_REASON_MESSAGES: Record<string, string> = {
  offseason: 'Opens once the regular season starts.',
  no_playoff_format: 'This league has no playoff format set yet.',
  no_rankings_data: 'Not enough roster data for this league yet.',
  unavailable: 'Not available for this league right now.',
  no_sleeper_username_linked: 'Link your Sleeper username to play.',
  not_a_member_of_league: 'Only members of this league can play.',
  espn_team_not_selected: 'Pick your team in this league to play.',
  no_roster: 'We could not find your team in this league.',
  locked: 'This week is locked.',
};

export function gamesReasonMessage(reason: string): string {
  return GAMES_REASON_MESSAGES[reason] ?? GAMES_REASON_MESSAGES.unavailable;
}

/** Where the empty state's next-step button should go for a reason. */
export function gamesReasonAction(reason: string): 'account' | 'home' {
  return reason === 'no_sleeper_username_linked' || reason === 'espn_team_not_selected' ? 'account' : 'home';
}

export function formatOdds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return `${Math.round(value)}%`;
}

/** Why championship odds are not shown (answers modules/playoff_simulator.py
 * `title_odds.reason`). */
export const TITLE_ODDS_REASON_MESSAGES: Record<string, string> = {
  unsupported_playoff_format:
    "Title odds are unavailable: this league's playoffs use a format we do not simulate yet (for example two-week rounds).",
  playoffs_underway: 'Title odds are unavailable: the playoffs have already started.',
  no_playoff_format: 'Title odds are unavailable: this league has no playoff format set.',
  unavailable: 'Title odds are unavailable right now.',
};

export function titleOddsUnavailableMessage(reason: string | undefined): string {
  return TITLE_ODDS_REASON_MESSAGES[reason ?? ''] ?? TITLE_ODDS_REASON_MESSAGES.unavailable;
}

/** Championship odds: a real but tiny chance reads '<1%', never '0%'. */
export function formatTitleOdds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '-';
  if (value <= 0) return '0%';
  if (value < 1) return '<1%';
  return `${Math.round(value)}%`;
}

/** "+4.2" / "-1.0" / "0.0" for a points change. */
export function formatDelta(value: number, digits = 1): string {
  const fixed = value.toFixed(digits);
  if (Number(fixed) === 0) return (0).toFixed(digits);
  return value > 0 ? `+${fixed}` : fixed;
}

/** Seed moves: negative is better (a lower seed number). */
export function seedChangeLabel(change: number): string {
  if (change === 0) return 'Seed unchanged';
  const places = Math.abs(change);
  return `${places} seed${places === 1 ? '' : 's'} ${change < 0 ? 'higher' : 'lower'}`;
}

export type WhatIfTone = 'positive' | 'negative' | 'neutral';

export function whatIfTone(change: { playoff_probability: number; within_noise: boolean }): WhatIfTone {
  if (change.within_noise) return 'neutral';
  return change.playoff_probability > 0 ? 'positive' : 'negative';
}

/** One plain sentence for the result; a move inside simulation noise says so
 * instead of claiming an effect. */
export function whatIfSummary(change: { playoff_probability: number; within_noise: boolean }): string {
  if (change.within_noise) return 'Within simulation noise. This move does not change your odds in a way we can measure.';
  const points = Math.abs(change.playoff_probability).toFixed(1);
  return change.playoff_probability > 0
    ? `Raises your playoff odds by ${points} points.`
    : `Lowers your playoff odds by ${points} points.`;
}

export const PICKEM_PHASE_LABEL: Record<string, string> = {
  open: 'Open',
  locked: 'Locked',
  final: 'Final',
};

/** Replace one matchup's pick locally (optimistic update). */
export function withPick<T extends { matchup_id: string; my_pick: string | null }>(
  matchups: T[],
  matchupId: string,
  rosterId: string,
): T[] {
  return matchups.map((m) => (m.matchup_id === matchupId ? { ...m, my_pick: rosterId } : m));
}

export function recordLabel(record: { correct: number; graded: number } | undefined): string {
  if (!record || record.graded === 0) return '0-0';
  return `${record.correct}-${record.graded - record.correct}`;
}

// ---------------------------------------------------------------------------
// Trade effect on odds (POST .../trade-odds-effect). Mirrored on web and mobile.
// ---------------------------------------------------------------------------

export interface TradeOddsEffectResult {
  reason: string;
  picks_excluded?: boolean;
  baseline?: { playoff_probability: number; title_probability?: number | null };
  scenario?: { playoff_probability: number; title_probability?: number | null };
  change?: {
    playoff_probability: number;
    title_probability?: number | null;
    within_noise: boolean;
    title_within_noise?: boolean;
  };
  margin_points?: number;
  trials?: number;
  slope_fitted?: boolean;
  weeks_remaining?: number;
}

export interface TradeOddsView {
  tone: WhatIfTone;
  headline: string;
  titleLine: string | null;
  detail: string;
  notes: string[];
}

/** Everything the odds row shows, or null when there is nothing real to show
 * (offseason, no games left, invalid package, simulator unavailable): the row
 * is omitted rather than filled with a guess. */
export function tradeOddsView(result: TradeOddsEffectResult | null | undefined): TradeOddsView | null {
  if (!result || result.reason || !result.baseline || !result.scenario || !result.change) return null;
  const { baseline, scenario, change } = result;
  const move = change.within_noise ? 'no measurable change' : `${formatDelta(change.playoff_probability)} pts`;
  const headline = `Playoff odds ${formatOdds(baseline.playoff_probability)} to ${formatOdds(scenario.playoff_probability)} (${move})`;
  let titleLine: string | null = null;
  if (baseline.title_probability != null && scenario.title_probability != null) {
    const titleMove =
      change.title_within_noise || change.title_probability == null
        ? 'no measurable change'
        : `${formatDelta(change.title_probability)} pts`;
    titleLine = `Title odds ${formatTitleOdds(baseline.title_probability)} to ${formatTitleOdds(scenario.title_probability)} (${titleMove})`;
  }
  const parts: string[] = [];
  if (result.margin_points != null) parts.push(`margin of error about ${result.margin_points.toFixed(1)} pts`);
  if (result.trials) parts.push(`${result.trials.toLocaleString('en-US')} simulated seasons`);
  if (result.weeks_remaining) parts.push(`${result.weeks_remaining} weeks left`);
  const notes: string[] = [];
  if (result.picks_excluded) notes.push('Draft picks are not counted in these odds.');
  if (result.slope_fitted === false) notes.push('Early-season estimate: too few games played to calibrate to this league.');
  return { tone: whatIfTone(change), headline, titleLine, detail: parts.join(', '), notes };
}

/** Season-odds line for the Dashboard strip (GET .../games/season-sim, free).
 * Title odds are included only when the simulator says they are available;
 * returns null (strip hidden) whenever there is nothing real to show. */
export function seasonOddsLine(
  data:
    | {
        reason?: string;
        my_team?: {
          playoff_probability: number;
          title_probability?: number | null;
          clinched?: boolean;
          eliminated?: boolean;
        } | null;
        title_odds?: { available: boolean; reason: string };
        weeks_remaining?: number;
        trials?: number;
        slope_fitted?: boolean;
      }
    | null
    | undefined,
): { headline: string; caption: string } | null {
  if (!data || data.reason || !data.my_team) return null;
  const mine = data.my_team;
  const playoff = mine.clinched
    ? 'Playoffs clinched'
    : mine.eliminated
      ? 'Out of playoff contention'
      : `Playoff odds ${formatOdds(mine.playoff_probability)}`;
  const titleAvailable = data.title_odds?.available === true && mine.title_probability != null;
  const headline = titleAvailable ? `${playoff} · Title odds ${formatTitleOdds(mine.title_probability)}` : playoff;
  const caption = [
    data.weeks_remaining ? `${data.weeks_remaining} weeks left` : null,
    data.trials ? `${data.trials.toLocaleString('en-US')} simulated seasons` : null,
    data.slope_fitted === false ? 'early-season estimate' : null,
  ]
    .filter(Boolean)
    .join(', ');
  return { headline, caption: caption ? `Rest-of-season simulation: ${caption}.` : '' };
}
