import { BEGINNER_HELP } from './experienceCopy.ts';
import { EST_SF_NOTE } from './adpPresentation.ts';
import { TERMS } from './terms.ts';

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
 * - Franchise Rank: franchise_score = the unweighted value of starters + top bench above replacement
 *   (raw_roster_score; depth is capped, not headcount) + draft_capital.
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
  // "Power" / "Power Rank" is the older name for This season; metric ids and API fields keep it.
  powerRank: { label: TERMS.thisSeason, definition: BEGINNER_HELP.powerRank },
  rosterPower: {
    label: "Roster Power",
    definition:
      "The strength score behind This season: your best possible starting lineup at full value plus a small credit for your top bench players.",
  },
  franchiseRank: { label: TERMS.longTerm, definition: BEGINNER_HELP.franchiseRank },
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
      "Future rookie draft picks (like a 2027 1st) count as tradable dynasty assets with their own value, shown alongside your players in trades and in your Long term rank.",
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
  teamStance: { label: "Team stance", definition: BEGINNER_HELP.tradeHubPosture },
  evaluationLens: {
    label: "Evaluation lens",
    definition:
      "How players are valued across the app. Dynasty weighs future upside alongside this year, Rebuild weights youth and draft picks most, and Redraft counts this season only. Change it from the league menu in the header.",
  },
  value: {
    label: "Value",
    definition:
      "A player's worth under this league's settings and your evaluation lens, on one scale used across the app. Higher is better.",
  },
  marketAdp: {
    label: "Market ADP",
    definition:
      "Average draft position: where a player is actually being picked in public drafts. Next to it, our rank is where FantasyDesk values the same player, so a gap shows who the market may be missing.",
  },
  estSf: { label: "Est. SF", definition: EST_SF_NOTE },
  faab: { label: "FAAB", definition: BEGINNER_HELP.faab },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;
