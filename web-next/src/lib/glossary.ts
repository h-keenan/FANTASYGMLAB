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
  dynasty: {
    label: "Dynasty",
    definition:
      "A fantasy format where you keep your players from year to year instead of starting over every season, so young players and draft picks matter.",
  },
  pqv: {
    label: "PQV (Player Quick View)",
    definition:
      "The quick summary card for one player: his value, overall rating (OVR), tier and what the app suggests doing with him.",
  },
  value: { label: "Value", definition: BEGINNER_HELP.playerValue },
  tier: { label: "Tier", definition: BEGINNER_HELP.playerTier },
  picks: {
    label: "Draft picks",
    definition:
      "Rookie draft picks you own can be traded like players. In dynasty they are worth real value, and they count toward your Franchise Rank.",
  },
  superflex: {
    label: "Superflex",
    definition:
      "A lineup rule that lets you start a second quarterback in a flex spot. Quarterbacks become more valuable because every team wants two. Values here follow your league's lineup rules.",
  },
  tep: {
    label: "TEP (Tight End Premium)",
    definition:
      "A scoring rule that gives tight ends extra points for each catch, which makes good tight ends worth more. Values here follow your league's scoring rules.",
  },
  faab: { label: "FAAB", definition: BEGINNER_HELP.faab },
  taxi: {
    label: "Taxi squad",
    definition:
      "A set of extra roster spots, in leagues that have them, for young players you want to stash without using a regular roster spot. Each league sets its own rules for who can go there.",
  },
  posture: {
    label: "Team Situation (posture)",
    definition:
      "How you are building your team: rebuilding, competing, or balanced. Trade ideas weigh player age and draft picks to match. It is your call, and you can change it any time.",
  },
  buyLow: { label: "Buy Low", definition: BEGINNER_HELP.impactBuyLow },
  sellHigh: { label: "Sell High", definition: BEGINNER_HELP.impactSellHigh },
} as const;

/** The jargon explained under Settings (web Account, mobile More), so the
 * full glossary is reachable from one place on both platforms. */
export const SETTINGS_GLOSSARY_TERMS: GlossaryKey[] = [
  "dynasty",
  "pqv",
  "value",
  "tier",
  "picks",
  "superflex",
  "tep",
  "faab",
  "taxi",
  "posture",
  "buyLow",
  "sellHigh",
];

export type GlossaryKey = keyof typeof GLOSSARY;
