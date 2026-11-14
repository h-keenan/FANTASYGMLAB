// Twin file: web-next/src/lib/simTeamIdentity.ts and mobile/src/lib/simTeamIdentity.ts stay identical.
//
// The ONE way a Fantasy Sim team is shown: its generated logo (SimCrest, seed + colours in lib/simCrest.ts) next to its name, through
// the SimTeamIdentity component (web components/SimTeamIdentity.tsx, app components/SimTeamIdentity.tsx). Sim team names are never
// rendered with a real-league TeamAvatar (initials circle) and never ellipsized: they walk the fit ladder below.
// docs/ui-patterns.md, "Team identity (Fantasy Sim)". Guarded by lib/simTeamIdentityRule.test.ts.

/** The size table, like PlayerAvatarSlot: pick a slot by what the row is, never a raw pixel number. Logo size in px. */
export const SIM_TEAM_SIZES = {
  /** Inline in a sentence or a "via Team" label. */
  inline: 16,
  /** Header chip, compact list rows (feed, trade partner line). */
  chip: 20,
  /** Standings, schedule, league and draft-board rows. */
  row: 28,
  /** Trade partner cards, matchup headers, recap result sides. */
  card: 44,
  /** Hero zones (recap hero, season champion). */
  hero: 56,
  /** The team sheet header. */
  sheet: 72,
} as const;
export type SimTeamSize = keyof typeof SIM_TEAM_SIZES;

export interface SimTeamNameFit {
  /** Fit stage 0 = full name on one line, 1 = wrapped to at most two balanced lines, 2 = wrapped and one font step smaller. */
  stage: 0 | 1 | 2;
  /** Font-size multiplier of the caller's own size. */
  scale: number;
  /** The line may wrap (balanced). Never false for stage >= 1. */
  wrap: boolean;
}

/** Longest name (characters) that is comfortable on one line / two lines at the caller's size, per layout width. */
const ONE_LINE = { wide: 22, narrow: 13 } as const;
const TWO_LINES = { wide: 40, narrow: 26 } as const;

/**
 * The fit ladder for a team name (the same idea as lib/playerNameFit.ts, but a team name is never shortened to an initial):
 *   0 full name, one line        "Trade Deadline Titans"
 *   1 wrap to two balanced lines "Trade Deadline / Titans"
 *   2 one font step smaller, still wrapping (very long names)
 * Pure (no measuring) so web and app pick the same stage; `narrow` is true for stacked/centered layouts (the recap hero sides).
 */
export function simTeamNameFit(name: string | null | undefined, narrow = false): SimTeamNameFit {
  const len = (name ?? "").replace(/\s+/g, " ").trim().length;
  const w = narrow ? "narrow" : "wide";
  if (len <= ONE_LINE[w]) return { stage: 0, scale: 1, wrap: false };
  if (len <= TWO_LINES[w]) return { stage: 1, scale: 1, wrap: true };
  return { stage: 2, scale: 0.88, wrap: true };
}
