/**
 * Experience-level copy (mobile). Mirrors web-next/src/lib/experienceCopy.ts:
 * the one place that decides what a beginner sees differently from an
 * advanced user, based on the onboarding answer ("How much dynasty
 * experience do you have?") stored through POST /v1/preferences as
 * `experience_level` ("beginner" | "advanced" | null).
 *
 * Copy only, never features:
 * - "beginner": key first-run surfaces add short plain-language helper text
 *   and spell out a few abbreviations.
 * - "advanced" and null (unanswered, skipped, or an account older than the
 *   question): today's terse copy, unchanged. `label()` returns the
 *   caller's current label and `help()` returns null.
 *
 * The BEGINNER_HELP and BEGINNER_LABELS blocks below are byte-identical to
 * web's; a web-next test compares them, so edit both files together. Each
 * explanation describes what the engine actually computes (source noted
 * per entry). Pure TS (no React Native imports) so node --test can run it.
 */

export type ExperienceLevel = "beginner" | "advanced";
/** null = never answered. Treated exactly like "advanced". */
export type ExperienceLevelSetting = ExperienceLevel | null;

export function normalizeExperienceLevel(value: unknown): ExperienceLevelSetting {
  return value === "beginner" || value === "advanced" ? value : null;
}

export const BEGINNER_HELP = {
  // Dashboard (services/mobile_api_service.py get_league_dashboard,
  // modules/league_rankings.py build_league_display_frame /
  // add_league_detail_ranks, modules/team_eval.py
  // _score_starter_weighted_roster).
  dashboardGamePlan:
    "Today lists the roster moves that would help your team most right now, most urgent first.",
  dashboardNothingUrgent:
    "No move is needed right now. Before game day, check Matchup to confirm your lineup is set in your league app.",
  dashboardSnapshot:
    "Team Snapshot ranks your team against every other team in this league. #1 is best, and T- means tied.",
  powerRank:
    "How strong your team is this season: the value of your best possible starting lineup, plus a small credit for bench depth.",
  franchiseRank:
    "Your long-term outlook: the dynasty value of your whole roster plus your draft picks.",
  starterStrength: "The combined value of your best possible starting lineup.",
  benchStrength: "The combined value of your best players who don't make that starting lineup.",
  averageAge:
    "The average age of your rostered players. Dynasty value drops once players pass their prime, earliest for running backs.",

  // Trade Analyzer verdict (modules/trade_offer_analyzer.py
  // decide_offer_verdict, modules/trade_analyzer_fit.py value_delta).
  verdictAccept: "You get back more value than you send, and the deal doesn't hurt how your roster fits together.",
  verdictCounter:
    "You'd send more value than you get back. It's close enough to negotiate, but not worth accepting as offered.",
  verdictDecline:
    "You'd send far more value than you get back, or the deal clearly hurts how your roster fits together.",
  verdictFair: "Value and roster fit come out roughly even, so either answer can be right.",
  analyzerValueBalance:
    "The total value you receive minus the total value you send, using this league's player values. A positive number means you gain value.",
  analyzerConfidence:
    "How clear-cut the verdict is, based on the size of the value gap and how much the deal helps or hurts your roster. A close call sits near the line between two verdicts. It isn't a prediction.",

  // Trade Hub ideas (modules/trade_ideas.py trade_gain,
  // _trade_confidence_context, evaluate_trade_market_realism;
  // modules/trade_hub_engine.py _classify_impact_tag).
  tradeHubIntro:
    "Each idea is a trade built for your roster with one specific partner. You send is what you give up and You get is what comes back.",
  tradeHubPosture:
    "Posture is how you're building your team: competing now, building for later, or in between. Ideas weigh player age and draft picks to match, so values here can differ slightly from Waivers or the Dashboard. Change it under Team Situation.",
  tradeHubHold:
    "Holding means making no trade. It is a real answer: a trade only helps if it clearly beats keeping your roster as it is.",
  ideaBalance:
    "The value you get minus the value you send, using this league's player values. A positive number means you gain value.",
  ideaConfidence:
    "How well this idea holds up: whether the other manager would plausibly accept, how well it fits both rosters, and how clear the reasons are. It isn't a prediction.",
  ideaRealism:
    "How likely the other manager is to find this fair enough to accept, based on the value each side gives up and what their roster needs.",
  impactHighImpact: "High Impact means this idea has high confidence.",
  impactBuyLow:
    "Buy Low means you'd get a backup or committee player whose role could grow, before his price catches up.",
  impactSellHigh:
    "Sell High means you'd send a player whose usage has dropped over recent weeks, or whose starting role looks at risk, while his value still reflects the bigger role.",

  // Waivers (services/mobile_api_service.py get_league_waivers,
  // modules/waivers_ui.py waiver_confidence_label and FAAB guidance).
  waiversIntro:
    "Free agents are players no team in your league has on its roster. Priority Adds lists the ones who fill a need on your roster first.",
  waiverValue: "Value is the player's worth under this league's settings, on the same scale used across the app. Higher is better.",
  averageWireValue: "The average value of every free agent currently available in this league.",
  faab:
    "FAAB (Free Agent Acquisition Budget) is the money your league gives each team to bid on free agents. The suggested bid is the share of your remaining budget this add is worth.",
  waiverConfidence:
    "High means the player fills a real need on your roster. Medium means strong value without a specific need. Low means a depth add.",

  // Player value and tier labels (modules/rankings.py valuation model,
  // modules/player_quick_view.py _overall_rating, modules/player_tiers.py
  // assign_player_tiers).
  playerValue:
    "Value blends dynasty market prices, age, production, positional scarcity, opportunity and role, then adjusts for this league's scoring and lineup rules. Use it to compare players, not as a points projection.",
  overallRating:
    "Overall (1-99) shows where this player's value ranks among players at the same position. Higher means closer to the top of the position.",
  playerTier:
    "Tier groups players mostly by how their value ranks across the whole player pool: Generational is roughly the top 1%, Elite the top 2.5%, Impact Starter the top 6%, Starter the top 16% and Contributor the top third. A player with no current role is capped at Committee / Role.",
} as const;

export type BeginnerHelpKey = keyof typeof BEGINNER_HELP;

/** Labels that are abbreviated or jargon for a beginner. An advanced user
 * keeps whatever label the page already passes in. */
export const BEGINNER_LABELS = {
  averageAge: "Average Age",
  averageWireValue: "Average Free-Agent Value",
  yourFaab: "Your Waiver Budget (FAAB)",
  ideaRealism: "Partner Acceptance",
} as const;

export type BeginnerLabelKey = keyof typeof BEGINNER_LABELS;

const VERDICT_HELP_KEY: Record<string, BeginnerHelpKey> = {
  ACCEPT: "verdictAccept",
  COUNTER: "verdictCounter",
  DECLINE: "verdictDecline",
  FAIR: "verdictFair",
};

const IMPACT_TAG_HELP_KEY: Record<string, BeginnerHelpKey> = {
  high_impact: "impactHighImpact",
  buy_low: "impactBuyLow",
  sell_high: "impactSellHigh",
};

export interface ExperienceCopy {
  level: ExperienceLevelSetting;
  isBeginner: boolean;
  /** The beginner explanation for `key`, or null for advanced/unset. */
  help: (key: BeginnerHelpKey) => string | null;
  /** The beginner label for `key`, or `advancedLabel` (today's copy). */
  label: (key: BeginnerLabelKey, advancedLabel: string) => string;
  /** Trade Analyzer's `ui_verdict` (ACCEPT/COUNTER/DECLINE/FAIR) -> help. */
  verdictHelp: (uiVerdict: string | null | undefined) => string | null;
  /** Trade Hub's `impact_tag` (high_impact/buy_low/sell_high) -> help. */
  impactTagHelp: (tag: string | null | undefined) => string | null;
}

export function experienceCopy(level: ExperienceLevelSetting): ExperienceCopy {
  const isBeginner = level === "beginner";
  const help = (key: BeginnerHelpKey) => (isBeginner ? BEGINNER_HELP[key] : null);
  return {
    level,
    isBeginner,
    help,
    label: (key, advancedLabel) => (isBeginner ? BEGINNER_LABELS[key] : advancedLabel),
    verdictHelp: (uiVerdict) => {
      const key = VERDICT_HELP_KEY[(uiVerdict || "").trim().toUpperCase()];
      return key ? help(key) : null;
    },
    impactTagHelp: (tag) => {
      const key = IMPACT_TAG_HELP_KEY[(tag || "").trim()];
      return key ? help(key) : null;
    },
  };
}
