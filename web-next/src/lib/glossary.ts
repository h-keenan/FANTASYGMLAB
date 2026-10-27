import { BEGINNER_HELP } from "./experienceCopy";

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
 * - Player Quick View / Draft Picks / Superflex / TEP added 2026-10-27
 *   (onboarding audit P1, "expand the glossary past 7 terms"):
 *   PlayerQuickView.tsx (the player popup these onboarding slides describe),
 *   modules/draft_assistant.py pick_label (how a pick is named), and
 *   modules/methodology_page.py's required user-facing phrases for how this
 *   app already describes Superflex/2QB and tight-end premium leagues.
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
  pqv: {
    label: "Player Quick View (PQV)",
    definition:
      "The player popup you open by tapping a player row: value, usage, and roster fit without leaving the page.",
  },
  draftPicks: {
    label: "Draft Picks",
    definition:
      "Future rookie draft picks (like a 2027 1st) count as tradable dynasty assets with their own value, shown alongside your players in trades and Franchise Rank.",
  },
  superflex: {
    label: "Superflex",
    definition:
      "A league format where a second quarterback can start in a FLEX spot, which raises quarterback value leaguewide.",
  },
  tep: {
    label: "TEP (Tight End Premium)",
    definition:
      "A scoring format that gives tight ends bonus points per reception, raising their dynasty value relative to other positions.",
  },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
