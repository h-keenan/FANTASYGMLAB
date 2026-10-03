/**
 * Crown-worthy prestige banding for a player's LEAGUE-WIDE/POOL position
 * rank (e.g. the "RB1"/"WR3" badge) — never a team-roster-relative rank.
 * This app has no team-roster-relative position rank anywhere (confirmed by
 * audit): `RankedPlayer.position_rank` (PlayersScreen, GM Targets, Compare)
 * is the league-global canonical rank, and `WaiverPlayer.position_rank`
 * (Waivers) is wire-relative to the free-agent pool — neither is "this
 * player's rank on your own fantasy roster."
 *
 * coridian_ (Discord): "where it has RB1 and RB2, that's confusing for some
 * people because some people might think that would mean that there are
 * [RB]2 on their own team, so we need a way to distinguish league wide
 * rankings to team rankings, so maybe the league wide rankings should have
 * a crown on it with prestige colors ... that crown would be on top of the
 * overall number, so the whole background on that overall module would be
 * the color of the crown."
 *
 * Bands the top of that rank into the app's existing gold/silver/bronze
 * award-tier palette (theme.ts's `awardTierColor` — the same hues
 * AwardsStrip already uses, not a new palette) so OverallRatingBadge can
 * swap its usual percentile tint for a crowned, prestige-tinted fill ONLY
 * for a genuinely global/pool-wide top rank. Every rank outside the band
 * (6th or worse at the position) fades back to the ordinary plain/percentile
 * treatment — no crown, no tint change — rather than inventing a fourth
 * color for "not special."
 */

import { awardTierColor } from '../theme';

export type PositionRankPrestigeTier = 'gold' | 'silver' | 'bronze';

export interface PositionRankPrestige {
  tier: PositionRankPrestigeTier | null;
  color: string | null;
}

const NO_PRESTIGE: PositionRankPrestige = { tier: null, color: null };

export function positionRankPrestige(
  rank: number | null | undefined,
  isDark = true,
): PositionRankPrestige {
  if (rank == null || !Number.isFinite(rank) || rank < 1) return NO_PRESTIGE;
  if (rank === 1) return { tier: 'gold', color: awardTierColor('gold', isDark) };
  if (rank <= 3) return { tier: 'silver', color: awardTierColor('silver', isDark) };
  if (rank <= 5) return { tier: 'bronze', color: awardTierColor('bronze', isDark) };
  return NO_PRESTIGE;
}
