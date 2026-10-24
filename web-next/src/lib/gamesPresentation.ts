/**
 * Games (Season Simulator + Pick'em) presentation helpers. Pure; mirrored by
 * mobile/src/lib/gamesPresentation.ts. Every string here answers a real
 * `reason` code from modules/games.py or modules/playoff_simulator.py.
 */

export const GAMES_REASON_MESSAGES: Record<string, string> = {
  offseason: "Opens once the regular season starts.",
  no_playoff_format: "This league has no playoff format set yet.",
  no_rankings_data: "Not enough roster data for this league yet.",
  unavailable: "Not available for this league right now.",
  no_sleeper_username_linked: "Link your Sleeper username to play.",
  not_a_member_of_league: "Only members of this league can play.",
  espn_team_not_selected: "Pick your team in this league to play.",
  no_roster: "We could not find your team in this league.",
  locked: "This week is locked.",
};

export function gamesReasonMessage(reason: string): string {
  return GAMES_REASON_MESSAGES[reason] ?? GAMES_REASON_MESSAGES.unavailable;
}

/** Where the empty state's next-step button should go for a reason. */
export function gamesReasonAction(reason: string): "account" | "dashboard" {
  return reason === "no_sleeper_username_linked" || reason === "espn_team_not_selected" ? "account" : "dashboard";
}

export function formatOdds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${Math.round(value)}%`;
}

/** Why championship odds are not shown (answers modules/playoff_simulator.py
 * `title_odds.reason`). */
export const TITLE_ODDS_REASON_MESSAGES: Record<string, string> = {
  unsupported_playoff_format:
    "Title odds are unavailable: this league's playoffs use a format we do not simulate yet (for example two-week rounds).",
  playoffs_underway: "Title odds are unavailable: the playoffs have already started.",
  no_playoff_format: "Title odds are unavailable: this league has no playoff format set.",
  unavailable: "Title odds are unavailable right now.",
};

export function titleOddsUnavailableMessage(reason: string | undefined): string {
  return TITLE_ODDS_REASON_MESSAGES[reason ?? ""] ?? TITLE_ODDS_REASON_MESSAGES.unavailable;
}

/** Championship odds: a real but tiny chance reads "<1%", never "0%". */
export function formatTitleOdds(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  if (value <= 0) return "0%";
  if (value < 1) return "<1%";
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
  if (change === 0) return "Seed unchanged";
  const places = Math.abs(change);
  return `${places} seed${places === 1 ? "" : "s"} ${change < 0 ? "higher" : "lower"}`;
}

export type WhatIfTone = "positive" | "negative" | "neutral";

export function whatIfTone(change: { playoff_probability: number; within_noise: boolean }): WhatIfTone {
  if (change.within_noise) return "neutral";
  return change.playoff_probability > 0 ? "positive" : "negative";
}

/** One plain sentence for the result; a move inside simulation noise says so
 * instead of claiming an effect. */
export function whatIfSummary(change: { playoff_probability: number; within_noise: boolean }): string {
  if (change.within_noise) return "Within simulation noise. This move does not change your odds in a way we can measure.";
  const points = Math.abs(change.playoff_probability).toFixed(1);
  return change.playoff_probability > 0
    ? `Raises your playoff odds by ${points} points.`
    : `Lowers your playoff odds by ${points} points.`;
}

export const PICKEM_PHASE_LABEL: Record<string, string> = {
  open: "Open",
  locked: "Locked",
  final: "Final",
};

export function pickemPhaseColor(phase: string | undefined): string {
  if (phase === "open") return "var(--color-success)";
  if (phase === "locked") return "var(--color-warning)";
  return "var(--color-text-muted)";
}

/** Replace one matchup's pick locally (optimistic update). */
export function withPick<T extends { matchup_id: string; my_pick: string | null }>(
  matchups: T[],
  matchupId: string,
  rosterId: string,
): T[] {
  return matchups.map((m) => (m.matchup_id === matchupId ? { ...m, my_pick: rosterId } : m));
}

export function recordLabel(record: { correct: number; graded: number } | undefined): string {
  if (!record || record.graded === 0) return "0-0";
  return `${record.correct}-${record.graded - record.correct}`;
}
