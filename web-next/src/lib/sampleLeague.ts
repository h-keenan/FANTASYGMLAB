/**
 * Static SAMPLE league shown to users with no league connected yet
 * (route /sample-league; mobile twin: mobile/src/lib/sampleLeague.ts, kept
 * identical in content -- sampleLeague.test.ts enforces it).
 *
 * Hard rules: everything here is fictional and always presented with a
 * "Sample league" label. No real user, league or roster data, no network
 * calls, no writes, no analytics (the route is on the analytics deny-list).
 * Names are deliberately obvious placeholders, not real NFL players.
 */

export const SAMPLE_ROUTE = "/sample-league";
export const SAMPLE_LEAGUE_NAME = "Sample Dynasty League";
export const SAMPLE_TEAM_NAME = "Demo Squad";
export const SAMPLE_BANNER_TITLE = "Sample league";
export const SAMPLE_BANNER_BODY = "Made-up players and numbers so you can look around. Nothing here is your data.";
export const SAMPLE_CTA_LABEL = "Connect your real league";
/** Where the CTA goes: the existing Add-a-league flow. */
export const SAMPLE_CONNECT_ROUTE = "/connect-league";
export const SAMPLE_ENTRY_LABEL = "Explore a sample league first";
/** Prominent button label on the landing page and the connect step / error states. */
export const SAMPLE_TRY_LABEL = "Try a sample league";

export type SampleTab = "dashboard" | "roster" | "game_plan" | "trade";
export const SAMPLE_TABS: { value: SampleTab; label: string }[] = [
  { value: "dashboard", label: "Dashboard" },
  { value: "roster", label: "Roster" },
  { value: "game_plan", label: "Game Plan" },
  { value: "trade", label: "Trade" },
];

export interface SamplePlayer {
  id: string;
  name: string;
  position: "QB" | "RB" | "WR" | "TE";
  age: number;
  /** Illustrative 0-100 dynasty score, not a real valuation. */
  value: number;
  note: string;
}

export const SAMPLE_ROSTER: SamplePlayer[] = [
  { id: "s1", name: "Alex Sampleton", position: "QB", age: 24, value: 88, note: "Young franchise QB, long window" },
  { id: "s2", name: "Riley Demoway", position: "RB", age: 23, value: 82, note: "Workhorse role, rising" },
  { id: "s3", name: "Casey Placeholder", position: "RB", age: 29, value: 54, note: "Aging, value falling" },
  { id: "s4", name: "Jordan Mockford", position: "WR", age: 25, value: 79, note: "Target leader on his team" },
  { id: "s5", name: "Taylor Exampleton", position: "WR", age: 22, value: 71, note: "Breakout candidate" },
  { id: "s6", name: "Morgan Testwell", position: "WR", age: 31, value: 38, note: "Sell window closing" },
  { id: "s7", name: "Drew Fakerson", position: "TE", age: 26, value: 66, note: "Top-8 tight end" },
  { id: "s8", name: "Sam Dummings", position: "QB", age: 33, value: 41, note: "Veteran backup" },
];

export interface SampleGamePlanItem {
  kicker: string;
  headline: string;
  reason: string;
  cta: "roster" | "trade";
}

export const SAMPLE_GAME_PLAN: SampleGamePlanItem[] = [
  {
    kicker: "Top priority",
    headline: "Sell Casey Placeholder before his value drops further",
    reason:
      "Sample reasoning: he is 29 with a falling role, and contenders still pay for him. Weighing age, your RB depth and how many teams need a back.",
    cta: "trade",
  },
  {
    kicker: "Watch",
    headline: "Taylor Exampleton is trending up",
    reason: "Sample reasoning: snap share is climbing. Hold unless an offer clears his current value.",
    cta: "roster",
  },
  {
    kicker: "Waiver opportunity",
    headline: "Add a handcuff for Riley Demoway",
    reason: "Sample reasoning: your RB1 carries most of the workload and the backup is unrostered.",
    cta: "roster",
  },
];

export interface SampleTrade {
  partner: string;
  give: SamplePlayer[];
  get: SamplePlayer[];
}

export const SAMPLE_TRADE: SampleTrade = {
  partner: "Team Placeholder",
  give: [SAMPLE_ROSTER[2], SAMPLE_ROSTER[5]],
  get: [{ id: "p1", name: "Quinn Stubbs", position: "WR", age: 24, value: 90, note: "Partner's depth WR" }],
};

export type SampleVerdictTone = "success" | "warning" | "danger";
export interface SampleVerdict {
  label: string;
  tone: SampleVerdictTone;
  giveTotal: number;
  getTotal: number;
  gap: number;
}

/** Sample trade verdict: compares summed illustrative values. */
export function sampleTradeVerdict(trade: SampleTrade): SampleVerdict {
  const giveTotal = trade.give.reduce((sum, p) => sum + p.value, 0);
  const getTotal = trade.get.reduce((sum, p) => sum + p.value, 0);
  const gap = getTotal - giveTotal;
  if (gap >= 5) return { label: "Favors you", tone: "success", giveTotal, getTotal, gap };
  if (gap <= -5) return { label: "Favors them", tone: "danger", giveTotal, getTotal, gap };
  return { label: "Fair", tone: "warning", giveTotal, getTotal, gap };
}

// ---------------------------------------------------------------------------
// Sample Dashboard: fictional inputs for the REAL Dashboard modules (Today
// hero, rank strip, Watchlist & Alerts, League Activity, Team Snapshot). Each
// platform maps these to its own API shapes (lib/sampleDashboard.ts on web and
// mobile); nothing here is fetched or stored. Player ids are left empty on
// purpose so no avatar or player lookup is ever made.
// ---------------------------------------------------------------------------

export const SAMPLE_DASHBOARD_WEEK = 6;
export const SAMPLE_DASHBOARD_NOTE =
  "Sample Dashboard: every card, rank and number below is made up. Taps are turned off here; connect your league to open them.";
export const SAMPLE_BLOCKED_MESSAGE = "That opens in your real league. Connect your league to use it.";

export interface SampleThisWeekRow {
  key: "lineup" | "waiver" | "trade";
  status: string;
  tone: "positive" | "risk" | "waiver" | "trade" | "neutral";
  headline: string;
  why: string;
  cta_label: string;
  route: "matchup" | "waivers" | "trade_hub";
}

export const SAMPLE_THIS_WEEK_ROWS: SampleThisWeekRow[] = [
  {
    key: "lineup",
    status: "Set",
    tone: "positive",
    headline: "Your sample lineup looks ready",
    why: "Sample reasoning: all eight starters are healthy and none is on a bye.",
    cta_label: "Review lineup",
    route: "matchup",
  },
  {
    key: "waiver",
    status: "Add",
    tone: "waiver",
    headline: "A sample handcuff is available",
    why: "Sample reasoning: Riley Demoway carries most of the RB workload and his backup is unrostered.",
    cta_label: "Open waivers",
    route: "waivers",
  },
];

export interface SampleDashboardItem {
  category: "top_priority" | "watch" | "waiver_opportunity";
  headline: string;
  reason: string;
  destination: "trade_hub" | "waivers" | "my_team";
  tier_label: string;
}

export const SAMPLE_DASHBOARD_ITEMS: SampleDashboardItem[] = [
  {
    category: "top_priority",
    headline: SAMPLE_GAME_PLAN[0].headline,
    reason: SAMPLE_GAME_PLAN[0].reason,
    destination: "trade_hub",
    tier_label: "Priority",
  },
  {
    category: "watch",
    headline: "Taylor Exampleton is trending up",
    reason: "Sample reasoning: snap share is climbing. Hold unless an offer clears his current value.",
    destination: "my_team",
    tier_label: "",
  },
  {
    category: "watch",
    headline: "Morgan Testwell is losing usage",
    reason: "Sample reasoning: usage down 31% (sample figure) over three weeks; his sell window is closing.",
    destination: "my_team",
    tier_label: "",
  },
  {
    category: "waiver_opportunity",
    headline: "Add a handcuff for Riley Demoway",
    reason: "Sample reasoning: your RB1 carries most of the workload and the backup is unrostered.",
    destination: "waivers",
    tier_label: "",
  },
];

export const SAMPLE_SNAPSHOT = {
  wins: 4,
  losses: 2,
  powerRank: 3,
  franchiseRank: 2,
  averageAge: 25.8,
  starterRank: 4,
  benchRank: 7,
  injuredStarters: 0,
};

export interface SamplePulseTeam {
  team_name: string;
  transaction_activity_count: number;
  current_streak: number;
}

export const SAMPLE_PULSE_TEAMS: SamplePulseTeam[] = [
  { team_name: "Team Placeholder", transaction_activity_count: 14, current_streak: 1 },
  { team_name: "Mock Mavericks", transaction_activity_count: 6, current_streak: 4 },
  { team_name: "Example Eagles", transaction_activity_count: 3, current_streak: -3 },
  { team_name: SAMPLE_TEAM_NAME, transaction_activity_count: 5, current_streak: 2 },
];
