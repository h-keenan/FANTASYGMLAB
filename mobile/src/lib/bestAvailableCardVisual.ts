/**
 * Visual decision for Waivers' "Best Available by Position" trending-player
 * cards (`BestAvailableCard` in screens/WaiversScreen.tsx).
 *
 * coridian_ (Discord, this pass): "we can have the border be the prestige
 * color with a glowing effect, have the name of the prestige along the top,
 * have the overall top right and name bottom center middle. And whatever
 * else." Translated to a rule: only a player who actually holds a
 * league-wide top-5-at-position prestige tier (gold/silver/bronze — see
 * lib/positionRankPrestige.ts, the same tier `OverallRatingBadge`'s crown
 * already uses) gets the colored glow border + a "GOLD"/"SILVER"/"BRONZE"
 * label. Everyone else keeps the plain neutral card — per UI_MAGNA_CARTA.md
 * §14/§15 (border/glow rules), a colored glow on every card would be
 * decorative, not meaningful.
 *
 * Deliberately takes an already-resolved `tier` (from
 * `positionRankPrestige(positionRank, isDark)`) rather than re-deriving it
 * from a raw rank or reaching into `theme.ts` for the tier color itself:
 * `theme.ts` imports the real `react-native` package, whose source can't be
 * loaded by plain Node (it's Flow syntax, meant to go through Metro/Babel),
 * so anything that transitively imports it can't run under this project's
 * `node --experimental-strip-types --test` convention (mobile has no
 * jest/component-render test runner configured). Keeping this function's
 * only dependency on `positionRankPrestige.ts` a type-only import (erased
 * entirely by type stripping, never resolved at runtime) is what keeps it
 * unit-testable in isolation — see bestAvailableCardVisual.test.ts.
 * Call sites still get the actual tier *color* from
 * `positionRankPrestige(...).color` directly (same as OverallRatingBadge
 * already does), so there is no second copy of the gold/silver/bronze
 * palette anywhere.
 */

import type { PositionRankPrestigeTier } from './positionRankPrestige.ts';

export interface BestAvailableCardVisual {
  /** "GOLD" / "SILVER" / "BRONZE", or null for an untiered player — render
   * nothing for null rather than an empty placeholder label. */
  prestigeLabel: string | null;
  /** Whether the card should get the colored glow treatment. Only ever true
   * when a tier is present — glow must stay restrained to a meaningful
   * subset of cards, never applied uniformly. */
  glow: boolean;
}

export function bestAvailableCardVisual(
  tier: PositionRankPrestigeTier | null | undefined,
): BestAvailableCardVisual {
  if (!tier) return { prestigeLabel: null, glow: false };
  return { prestigeLabel: tier.toUpperCase(), glow: true };
}
