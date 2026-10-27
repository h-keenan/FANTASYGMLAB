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

/** The three-way onboarding answer. Additive to the legacy two-value level:
 * "new_fantasy" and "new_dynasty" both map to "beginner", "veteran" to
 * "advanced". null = never answered. */
export type ExperienceTier = "new_fantasy" | "new_dynasty" | "veteran";
export type ExperienceTierSetting = ExperienceTier | null;
/** Optional onboarding goal. Used only to suggest a Team Situation, never
 * to set anything on its own. null = not answered. */
export type PrimaryGoal = "win_now" | "rebuild" | "exploring";
export type PrimaryGoalSetting = PrimaryGoal | null;

export function normalizeExperienceTier(value: unknown): ExperienceTierSetting {
  return value === "new_fantasy" || value === "new_dynasty" || value === "veteran" ? value : null;
}

export function normalizePrimaryGoal(value: unknown): PrimaryGoalSetting {
  return value === "win_now" || value === "rebuild" || value === "exploring" ? value : null;
}

/** The legacy level a tier implies (what old app builds read). */
export function levelForTier(tier: ExperienceTier): ExperienceLevel {
  return tier === "veteran" ? "advanced" : "beginner";
}

/** The default tier for a legacy level, when only the level is known. */
export function tierForLevel(level: ExperienceLevel): ExperienceTier {
  return level === "advanced" ? "veteran" : "new_dynasty";
}

/** Team Situation values (api.ts TeamStance) a goal can suggest. */
export function stanceForGoal(goal: PrimaryGoalSetting): "competing" | "rebuilding" | null {
  if (goal === "win_now") return "competing";
  if (goal === "rebuild") return "rebuilding";
  return null;
}

/** One set of labels for onboarding and the Settings screens (web Account,
 * mobile More), so the same choice is never named two ways. */
export const EXPERIENCE_TIERS = {
  new_fantasy: {
    label: "New to fantasy",
    description: "Explain the basics. Plain words for every term, and the why behind each recommendation.",
  },
  new_dynasty: {
    label: "New to dynasty",
    description: "I play fantasy, but keeping players year to year is new. Explain the dynasty parts.",
  },
  veteran: {
    label: "Dynasty veteran",
    description: "Skip the explanations. Just the call, the value, and the confidence.",
  },
} as const;

export const PRIMARY_GOALS = {
  win_now: { label: "Win now", description: "Compete for a title this season." },
  rebuild: { label: "Build for the future", description: "Trade for youth and draft picks." },
  exploring: { label: "Just looking", description: "Not sure yet. Show me around." },
} as const;

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

  // Matchup, My Team, Playoff Odds and GM Plan (services/mobile_api_service.py
  // get_league_matchup / get_league_playoff_odds, modules/team_stance.py).
  matchupIntro:
    "This is your head-to-head for the week. Check your win probability and Suggested Moves, then make any lineup change in your league app before kickoff.",
  matchupWinProbability:
    "Win probability is your chance to win this week, based on both lineups' projected points. It isn't a guarantee.",
  myTeamIntro:
    "My Team shows your roster and how it stacks up. This week: make sure your best players are starting, and look at the bench for players worth trading or dropping.",
  myTeamValueTiers:
    "Value is a player's worth in this league (higher is better). A tier groups players of similar value, from Generational down to Contributor.",
  playoffOddsIntro:
    "Playoff Odds estimates each team's chance to make the playoffs. Low odds mean consider building for later; high odds mean add help now.",
  playoffOddsTerms:
    "Win probability is a team's chance to win a single game. Clinched means a playoff spot is locked in. Eliminated means it can no longer happen.",
  stanceRebuilding: "Rebuilding: you're trading for youth and draft picks, not this season's title.",
  stanceCompeting: "Competing: you're going for a title now, even if it costs future picks.",
  stanceBalanced: "Balanced: you want to stay competitive while keeping future flexibility.",
} as const;

export type BeginnerHelpKey = keyof typeof BEGINNER_HELP;

/** Plainer, shorter wording for "New to fantasy" accounts. Same facts as
 * BEGINNER_HELP (same source code), fewer terms. Keys not listed here fall
 * back to the BEGINNER_HELP line. */
export const NEW_FANTASY_HELP = {
  dashboardGamePlan:
    "A short to-do list for your team, with the most important move first. You don't have to do them all.",
  dashboardSnapshot:
    "Team Snapshot shows where your team stands compared to the other teams in your league. #1 is the best.",
  powerRank:
    "How strong your team is this season. It adds up the value of the best lineup you could start, plus a little for your backups.",
  franchiseRank:
    "How good your team looks over the long run. It adds up the value of every player you own and your draft picks.",
  verdictAccept: "You get back more than you give up, and your lineup still fits together. A good deal for you.",
  verdictCounter:
    "You'd give up more than you get back. It's close, so ask for a little more instead of saying yes right away.",
  verdictDecline: "You'd give up much more than you get back, or the trade would leave a hole in your lineup.",
  playerValue:
    "A number for how much a player is worth in your league. Higher is better. Use it to compare players, not to guess how many points he will score.",
  faab: "FAAB is a budget of pretend money your league gives you to bid on free agents. The suggested bid is how much of your remaining money this player is worth.",
  tradeHubPosture:
    "Posture is your plan for your team: win now, build for the future, or somewhere in between. Trade ideas lean toward that plan. You can change it under Team Situation.",
  tradeHubHold: "Holding means not trading. That is a real answer. Only trade when the deal clearly beats keeping your team as it is.",
} as const;


/** Labels that are abbreviated or jargon for a beginner. An advanced user
 * keeps whatever label the page already passes in. */
export const BEGINNER_LABELS = {
  averageAge: "Average Age",
  averageWireValue: "Average Free-Agent Value",
  yourFaab: "Your Waiver Budget (FAAB)",
  ideaRealism: "Partner Acceptance",
} as const;

export type BeginnerLabelKey = keyof typeof BEGINNER_LABELS;

/** Plain (not beginner-gated) next-step and orientation copy that must read
 * the same on web and mobile. A web test keeps the two maps byte-identical. */
export const PLAIN_COPY = {
  matchupRetryAction: "Try again",
  matchupSeasonSubtitle: "Check back when the season starts.",
  matchupDashboardAction: "Open Dashboard",
  matchupConnectAction: "Connect a league",
  gmPlanProTitle: "What Pro unlocks",
  gmPlanProBody:
    "A season headline for your team, your best trade paths, and roster-construction focus areas, all built from your Team Snapshot above.",
  onboardingDynastyNote:
    "Dynasty is the long-term fantasy format where you keep your players year to year. Pick the closest fit. You can change this anytime in Settings.",
  onboardingGoalTitle: "What's your goal this season? (optional)",
  teamSituationSuggestion:
    "Based on the goal you picked in onboarding, this is a suggestion only. Nothing changes until you tap it.",
} as const;

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
  tier: ExperienceTierSetting;
  isBeginner: boolean;
  /** True only for the "New to fantasy" tier (plainer wording). */
  isNewToFantasy: boolean;
  /** The beginner explanation for `key`, or null for advanced/unset. */
  help: (key: BeginnerHelpKey) => string | null;
  /** The beginner label for `key`, or `advancedLabel` (today's copy). */
  label: (key: BeginnerLabelKey, advancedLabel: string) => string;
  /** Trade Analyzer's `ui_verdict` (ACCEPT/COUNTER/DECLINE/FAIR) -> help. */
  verdictHelp: (uiVerdict: string | null | undefined) => string | null;
  /** Trade Hub's `impact_tag` (high_impact/buy_low/sell_high) -> help. */
  impactTagHelp: (tag: string | null | undefined) => string | null;
}

/** `tier` only refines the wording for "New to fantasy"; the level alone
 * (legacy accounts, old builds) behaves as before. A tier that disagrees
 * with the level is ignored. */
export function experienceCopy(
  level: ExperienceLevelSetting,
  tier: ExperienceTierSetting = null,
): ExperienceCopy {
  const isBeginner = level === "beginner";
  const isNewToFantasy = isBeginner && tier === "new_fantasy";
  const help = (key: BeginnerHelpKey) => {
    if (!isBeginner) return null;
    if (isNewToFantasy && key in NEW_FANTASY_HELP) return NEW_FANTASY_HELP[key as keyof typeof NEW_FANTASY_HELP];
    return BEGINNER_HELP[key];
  };
  return {
    level,
    tier,
    isBeginner,
    isNewToFantasy,
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
