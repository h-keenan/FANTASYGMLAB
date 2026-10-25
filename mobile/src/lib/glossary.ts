import { BEGINNER_HELP } from './experienceCopy.ts';

/**
 * The one glossary of fantasy/analytics jargon, with one-sentence
 * definitions that are shown to EVERYONE through the info affordance
 * (GlossaryNote) on Dashboard, Team and Portfolio views. mobile/src/lib/
 * glossary.ts is identical apart from the first import line (a web test keeps
 * them in sync).
 *
 * Definitions describe what the engine computes, and where they match a
 * BEGINNER_HELP line they reuse that exact text, so the beginner caption and
 * the glossary can never disagree. Sources:
 * - Power Rank / Roster Power: modules/league_rankings.py
 *   build_league_display_frame (power_score = team_eval
 *   _score_starter_weighted_roster total_score = best starting lineup + the
 *   top few bench players at BENCH_WEIGHT 0.18), ranked highest first.
 * - Franchise Rank: franchise_score = the unweighted value of the whole
 *   roster (raw_roster_score) + draft_capital.
 * - Starter / Bench Strength: starter_rank / bench_rank in
 *   add_league_detail_ranks, from starter_score / bench_score.
 * - OVR: modules/player_quick_view.py _overall_rating (0-99 percentile of
 *   the player's value among players at his position).
 */

export const GLOSSARY = {
  powerRank: { label: "Power Rank", definition: BEGINNER_HELP.powerRank },
  rosterPower: {
    label: "Roster Power",
    definition:
      "The strength score behind Power Rank: your best possible starting lineup at full value plus a small credit for your top bench players.",
  },
  franchiseRank: { label: "Franchise Rank", definition: BEGINNER_HELP.franchiseRank },
  starterStrength: { label: "Starter Strength", definition: BEGINNER_HELP.starterStrength },
  benchStrength: {
    label: "Bench Strength",
    definition:
      "The value of your best bench players (a limited number of them) that don't make your starting lineup, ranked against the other teams.",
  },
  ovr: { label: "OVR", definition: BEGINNER_HELP.overallRating },
  averageAge: { label: "Average Age", definition: BEGINNER_HELP.averageAge },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
