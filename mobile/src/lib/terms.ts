/**
 * The product glossary: ONE name per concept, used in every user-visible
 * string on web and mobile. Byte-identical to mobile/src/lib/terms.ts (a test
 * checks it), and src/lib/terms.test.ts fails when a retired term shows up in
 * user-visible copy again.
 *
 * Canonical names are the ones the Today page and the nav already use
 * (decided 2026-11-10, coridian_ "whatever's best"):
 *
 * - Today      The landing page: the briefing of what to do right now (top
 *              priority, then the next few moves). Was called "Dashboard"
 *              (route and code names keep that word), "Game Plan",
 *              "Today's Game Plan" and "Next Moves"; those are retired.
 * - Fantasy Sim  The draft-a-team-and-play-a-season game (/gm-game).
 * - Season Outlook  The playoff-odds and projected-finish forecast for a real
 *              league (GM Plan tab, Games tab). "Season Sim" is retired.
 * - GM Plan    The Pro season roadmap page (where you stand, trade paths,
 *              roster construction). Never used for the Today briefing.
 * - Pro        The paid tier. "Premium" is retired from UI copy (it stays in
 *              code, analytics and API field names). Exception: the league
 *              setting "TE Premium" / "Tight End Premium".
 *
 * - This season / Long term  The two team ranks. "Power" (Power Rank)
 *              is now "This season" and "Franchise" (Franchise Rank)
 *              is now "Long term" (decided 2026-11-16, F5 of the first-time-user
 *              audit). Metric ids, routes and API fields keep power/franchise.
 * - Watchlist  The one list of players you are tracking (Waivers tab, GM Plan
 *              tab, the header shortcut). "Watching" and "GM Targets" are
 *              retired; the route and API names (gm-targets) are unchanged.
 * - Ideas / Grade a trade  The Trades section tabs. "Hub" and "Analyzer" are
 *              retired as tab names (the page is still Trade Hub, the route
 *              /trade-analyzer).
 * - Your leagues  What "Home" is called outside a league (the league list).
 * - Depth Adds  The Waivers shortlist row of free agents who would add bench
 *              depth (it was "Bench Depth", which is also a team rank).
 * - Season Outlook is always named with its parent (GM Plan or Games); use
 *              seasonOutlookIn().
 *
 * Marketing prose may say "game plan" in lowercase ("a weekly game plan");
 * the retired terms are the capitalized product names.
 *
 * Add a retired term here with its replacement and the test enforces it.
 */
export const TERMS = {
  today: "Today",
  fantasySim: "Fantasy Sim",
  seasonOutlook: "Season Outlook",
  gmPlan: "GM Plan",
  pro: "Pro",
  thisSeason: "This season",
  longTerm: "Long term",
  watchlist: "Watchlist",
  tradeIdeas: "Ideas",
  gradeATrade: "Grade a trade",
  gradeATradeShort: "Grade",
  yourLeagues: "Your leagues",
  depthAdds: "Depth Adds",
} as const;

/** "Season Outlook" is never shown alone: it always names the page it lives on ("GM Plan > Season Outlook"). */
export function seasonOutlookIn(parent: string): string {
  return `${parent} > ${TERMS.seasonOutlook}`;
}

export interface RetiredTerm {
  /** Matches the retired wording inside a user-visible string. */
  pattern: RegExp;
  /** What to write instead. */
  use: string;
}

export const RETIRED_TERMS: RetiredTerm[] = [
  { pattern: /\bGame Plan\b/, use: TERMS.today },
  { pattern: /\bNext Moves?\b/, use: TERMS.today },
  { pattern: /\bPremium\b/, use: TERMS.pro },
  { pattern: /\bSeason Sim\b/, use: TERMS.seasonOutlook },
  { pattern: /\bPower Rank\b/, use: TERMS.thisSeason },
  { pattern: /\bFranchise Rank\b/, use: TERMS.longTerm },
  { pattern: /^Power$/, use: TERMS.thisSeason },
  { pattern: /^Franchise$/, use: TERMS.longTerm },
  { pattern: /\bGM Targets?\b/, use: TERMS.watchlist },
  { pattern: /^Watching$/, use: TERMS.watchlist },
  { pattern: /^Hub$/, use: TERMS.tradeIdeas },
  { pattern: /^Analyzer$/, use: TERMS.gradeATrade },
];

/** Phrases that contain a retired word legitimately (league settings, etc.). */
export const RETIRED_TERM_ALLOWLIST: RegExp[] = [/\bTE Premium\b/, /\bTight End Premium\b/];
