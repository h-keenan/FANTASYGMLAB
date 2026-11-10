/** Feature screenshots + one-line benefits shared by the signup carousel and the landing page. Keep in lockstep with mobile OnboardingScreen.tsx. */
export const ONBOARDING_FEATURES = [
  { key: "gameplan", title: "Today", benefit: "One clear top priority every time you open the app." },
  { key: "tradehub", title: "Trade Hub", benefit: "Trade ideas your league partners would actually accept." },
  { key: "matchup", title: "Matchup", benefit: "Win odds for your week, before kickoff." },
  { key: "planner", title: "Lineup Planner", benefit: "See what a swap does to your win odds." },
  { key: "pqv", title: "Player Quick View", benefit: "Value, usage, and fit for any player in one tap." },
  { key: "playoff", title: "Playoff Odds", benefit: "Simulated playoff odds for every team in your league." },
  { key: "tendencies", title: "Manager Tendencies", benefit: "Know how each manager trades before you pitch." },
  { key: "waivers", title: "Waivers", benefit: "Priority Adds ranked for your roster. Pro adds FAAB bid ranges." },
] as const;

/**
 * Signup onboarding is 2 steps (coridian_, 2026-10-23: "10 is insane";
 * 2026-11-10: level asked first, Connect info slide removed because the real
 * connect form follows): level -> value. These are the funnel `step` ids;
 * step_index is the position here (0, 1). Before the first change the ids were the 8 feature
 * keys (0-7), connect (8) and level (9). Keep in lockstep with mobile
 * OnboardingScreen.tsx.
 */
export const ONBOARDING_STEP_KEYS = ["level", "value"] as const;
export type OnboardingStepKey = (typeof ONBOARDING_STEP_KEYS)[number];

/** Screenshots the value step auto-advances through (inside step 1; they are not separate steps). */
export const ONBOARDING_VALUE_SLIDE_KEYS = ["gameplan", "tradehub", "matchup", "waivers"] as const;
export const ONBOARDING_VALUE_HEADLINE = "Know your best move every week.";
export const ONBOARDING_VALUE_SLIDE_MS = 3600;
