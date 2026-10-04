import type { QuickViewModel } from './api';

/** One sub-rating chip's input: a short caps tag plus its 0-99 rating
 * (same scale/curve as the headline OVR badge — see
 * modules.player_quick_view.sub_ratings). `rating` is `null` whenever the
 * backend's thin-pool gate (or, for Durability, a missing multiplier)
 * refused a number — never a fabricated value. */
export interface SubRating {
  label: string;
  rating: number | null | undefined;
}

/**
 * Market/Opportunity/Scarcity/Role/Durability, pulled off a QuickViewModel
 * in the fixed order the Model tab's chip row (PlayerDetailScreen's
 * ModelSection) and PlayerShareCard's "headline attributes" row both render
 * them in — one builder, two surfaces, so a player's share card and their
 * in-app Model tab can never disagree about these five numbers.
 */
export function playerSubRatings(
  model: Pick<
    QuickViewModel,
    'market_rating' | 'opportunity_rating' | 'scarcity_rating' | 'role_rating' | 'durability_rating'
  >,
): SubRating[] {
  return [
    { label: 'MKT', rating: model.market_rating },
    { label: 'OPP', rating: model.opportunity_rating },
    { label: 'SCR', rating: model.scarcity_rating },
    { label: 'ROLE', rating: model.role_rating },
    { label: 'DUR', rating: model.durability_rating },
  ];
}
