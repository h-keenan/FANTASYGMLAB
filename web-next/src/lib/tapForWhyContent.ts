import { BEGINNER_HELP } from "./experienceCopy";

// The one registry of "tap the number to see why" copy, keyed by metric id.
// Web and mobile render `TapForWhy` from this same table (byte-identical twin),
// so a metric never explains itself two different ways. Sentences reuse
// BEGINNER_HELP wherever a line already exists, so captions, glossary and this
// popover can never disagree. Rule: 1 to 3 plain sentences, no jargon that is
// not itself a registry key.

export type WhyMetricId =
  | "value"
  | "trade_value"
  | "ovr"
  | "rank"
  | "tier"
  | "grade"
  | "win_probability"
  | "playoff_odds"
  | "faab"
  | "balance"
  | "confidence"
  | "usage_trend"
  | "projection"
  | "age"
  | "power_rank"
  | "franchise_rank"
  | "starter_strength"
  | "bench_strength"
  | "posture"
  | "buy_low"
  | "sell_high";

export type WhyEntry = {
  id: WhyMetricId;
  /** Sheet heading. Plain words, not the jargon label. */
  title: string;
  /** 1 to 3 plain sentences. */
  sentences: readonly string[];
  /** Optional deeper reading, same-origin path. */
  learnMoreHref?: string;
  learnMoreLabel?: string;
};

const METHODOLOGY = "/methodology";

export const WHY_REGISTRY: Record<WhyMetricId, WhyEntry> = {
  value: {
    id: "value",
    title: "What Value means",
    sentences: [BEGINNER_HELP.playerValue],
    learnMoreHref: METHODOLOGY,
    learnMoreLabel: "How values are built",
  },
  // Fantasy Sim only: the 0-100 number AI teams use in trades. Never labeled plain "Value" or "VAL".
  trade_value: {
    id: "trade_value",
    title: "What trade value means",
    sentences: [
      "Trade value is how much this game's AI teams think a player or pick is worth in a trade, on a 0-100 scale where the top player is 100.",
      "It is not Overall (his rank at his position) and not a points projection. Use it to judge whether a trade is fair.",
    ],
  },
  ovr: {
    id: "ovr",
    title: "What OVR means",
    sentences: [BEGINNER_HELP.overallRating, "The chart shows the parts that make up this player's rating."],
    learnMoreHref: METHODOLOGY,
    learnMoreLabel: "How ratings are built",
  },
  rank: {
    id: "rank",
    title: "What this rank means",
    sentences: [BEGINNER_HELP.dashboardSnapshot],
  },
  tier: {
    id: "tier",
    title: "What this tier means",
    sentences: [BEGINNER_HELP.playerTier],
  },
  grade: {
    id: "grade",
    title: "What this grade means",
    sentences: [
      "The letter grade compares how this result scores against everyone else's, using this league's player values.",
      "A is the top of the range and D the bottom. It rates the decision, not luck.",
    ],
  },
  win_probability: {
    id: "win_probability",
    title: "Win probability",
    sentences: [BEGINNER_HELP.matchupWinProbability],
  },
  playoff_odds: {
    id: "playoff_odds",
    title: "Playoff odds",
    sentences: [BEGINNER_HELP.playoffOddsIntro, BEGINNER_HELP.playoffOddsTerms],
  },
  faab: {
    id: "faab",
    title: "FAAB bid",
    sentences: [BEGINNER_HELP.faab],
  },
  balance: {
    id: "balance",
    title: "Trade balance",
    sentences: [BEGINNER_HELP.analyzerValueBalance],
  },
  confidence: {
    id: "confidence",
    title: "Confidence",
    sentences: [BEGINNER_HELP.analyzerConfidence],
  },
  usage_trend: {
    id: "usage_trend",
    title: "Usage trend",
    sentences: [
      "Usage is how much a player is actually used: snaps, touches and targets over the last several games.",
      "Rising usage often comes before a value jump. Falling usage can be an early warning that his role is at risk.",
    ],
  },
  projection: {
    id: "projection",
    title: "Projection",
    sentences: [
      "The projection is the points we expect this player to score, based on his recent usage and the matchup.",
      "It is an estimate, not a promise. Value, not projection, drives dynasty trade math.",
    ],
  },
  age: {
    id: "age",
    title: "Age",
    sentences: [BEGINNER_HELP.averageAge],
  },
  // The team ranks on Today and My Team. Display names come from lib/terms.ts ("This season", "Long term"); the ids keep
  // the engine's power / franchise names.
  power_rank: {
    id: "power_rank",
    title: "What \"This season\" means",
    sentences: [BEGINNER_HELP.powerRank],
  },
  franchise_rank: {
    id: "franchise_rank",
    title: "What \"Long term\" means",
    sentences: [BEGINNER_HELP.franchiseRank],
  },
  starter_strength: {
    id: "starter_strength",
    title: "What starter strength means",
    sentences: [BEGINNER_HELP.starterStrength],
  },
  bench_strength: {
    id: "bench_strength",
    title: "What bench strength means",
    sentences: [BEGINNER_HELP.benchStrength],
  },
  posture: {
    id: "posture",
    title: "What posture means",
    sentences: [BEGINNER_HELP.tradeHubPosture],
  },
  buy_low: {
    id: "buy_low",
    title: "What Buy Low means",
    sentences: [BEGINNER_HELP.impactBuyLow],
  },
  sell_high: {
    id: "sell_high",
    title: "What Sell High means",
    sentences: [BEGINNER_HELP.impactSellHigh],
  },
};

export function whyEntry(id: WhyMetricId): WhyEntry {
  return WHY_REGISTRY[id];
}

/** Accessible name for the trigger, e.g. "Why: Value 82". */
export function whyTriggerLabel(id: WhyMetricId, spoken?: string): string {
  const entry = WHY_REGISTRY[id];
  return spoken ? `Why: ${spoken}` : `Why: ${entry.title}`;
}
