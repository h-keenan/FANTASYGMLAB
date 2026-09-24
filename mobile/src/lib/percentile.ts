import type { ThemeColors } from '../theme';

/**
 * Shared percentile presentation helpers — extracted out of
 * PlayerDetailScreen so the new MetricCard/PercentileBar components (and the
 * screen's own remaining StatCell usage for Model/Bio/Career) read the exact
 * same red -> gold -> green ramp instead of two copies drifting apart.
 * Pure presentation only: every value here comes from a percentile the
 * backend already computed (player_quick_view.py) — nothing is recomputed
 * or re-thresholded client-side.
 */

/** 1 -> "1st", 22 -> "22nd", 13 -> "13th". Teens are all "th" regardless of
 * their last digit, which is the case a naive last-digit switch gets wrong. */
export function ordinal(value: number): string {
  const rounded = Math.round(value);
  const lastTwo = Math.abs(rounded) % 100;
  const lastOne = Math.abs(rounded) % 10;
  if (lastTwo >= 11 && lastTwo <= 13) return `${rounded}th`;
  if (lastOne === 1) return `${rounded}st`;
  if (lastOne === 2) return `${rounded}nd`;
  if (lastOne === 3) return `${rounded}rd`;
  return `${rounded}th`;
}

/** "59 rush yards" says nothing about whether 59 is good for the position —
 * this is the peer-group answer the backend attaches to each stat. Absent
 * (null/undefined) whenever the position pool was too small to rank against,
 * in which case nothing renders rather than a made-up number. */
export function percentileLabel(percentile: number | null | undefined): string | null {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return null;
  return `${ordinal(percentile)} pctl`;
}

function mixHex(from: string, to: string, t: number): string {
  const parse = (hex: string) => [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
  const [r1, g1, b1] = parse(from);
  const [r2, g2, b2] = parse(to);
  const channel = (a: number, b: number) =>
    Math.round(a + (b - a) * t)
      .toString(16)
      .padStart(2, '0');
  return `#${channel(r1, r2)}${channel(g1, g2)}${channel(b1, b2)}`;
}

/** Reads the percentile's color off a red -> gold -> green ramp so "9th" and
 * "91st" don't arrive in the same flat blue. Anchored on the existing palette
 * (danger at 0, premium at 50, successBright at 100) and interpolated
 * channel-wise rather than bucketed into three flat bands, so neighbouring
 * stats stay distinguishable instead of snapping at a cutoff. Anything
 * unrankable keeps the old accentSoft. */
export function percentileColor(percentile: number | null | undefined, colors: ThemeColors): string {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) {
    return colors.accentSoft;
  }
  const clamped = Math.max(0, Math.min(100, percentile));
  if (clamped <= 50) return mixHex(colors.danger, colors.premium, clamped / 50);
  return mixHex(colors.premium, colors.successBright, (clamped - 50) / 50);
}

/** Best team in a group -> 100, worst -> 0. Several backend rank fields
 * (league_rankings.py's power_rank/draft_capital_rank/starter_rank/etc.)
 * only expose a dense rank (1 = best), never a raw 0-100 score, so this is
 * the honest way to turn "rank #3 of 12" into a percentile for the shared
 * percentile color ramp instead of fabricating a score. Originally lived
 * only in MyTeamScreen; promoted here once TeamsScreen needed the exact
 * same rank-to-percentile transform for every team in the league, not just
 * the caller's own. */
export function percentileFromRank(rank: number | null | undefined, totalTeams: number): number | null {
  if (rank == null || totalTeams <= 1) return null;
  return Math.round(((totalTeams - rank) / (totalTeams - 1)) * 100);
}

/** Real, not fabricated: the same percentile the badge text already shows,
 * just given a direction — at/above the 50th percentile reads as a trend
 * up, below it a trend down. Never a week-over-week delta (this app has no
 * such series for most stats). */
export function percentileTrendIcon(percentile: number | null | undefined): 'caret-up' | 'caret-down' | null {
  if (percentile === null || percentile === undefined || !Number.isFinite(percentile)) return null;
  return percentile >= 50 ? 'caret-up' : 'caret-down';
}
