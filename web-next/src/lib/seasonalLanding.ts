/**
 * Season-aware copy for the logged-out landing page and the public SEO chrome.
 *
 * Pure port of the calendar rule in modules/season_clock.py (clock_from_calendar) plus the
 * content sub-phase mapping in modules/external_ad_api.py (sub_phase), so the website and the
 * advertising API agree on "what is relevant right now". The server clock prefers Sleeper's
 * /state/nfl when reachable; the calendar rule is its documented fallback and is what a static,
 * network-free landing page can use. Fantasy playoffs are the reference weeks 15-17.
 */

export type SeasonStage =
  | "in_season"
  | "playoff_push"
  | "fantasy_playoffs"
  | "season_end"
  | "nfl_postseason"
  | "free_agency"
  | "draft_season"
  | "post_draft"
  | "training_camp";

export interface SeasonMoment {
  stage: SeasonStage;
  /** NFL season in effect (flips at kickoff). */
  season: number;
  /** Regular-season week, only while one is being played. */
  week: number | null;
}

export const FANTASY_PLAYOFF_WEEKS = [15, 16, 17] as const;
const REGULAR_SEASON_WEEKS = 18;
const WEEK_ROLLOVER_WEEKDAY = 1; // Tuesday (Mon=0), same as season_clock.WEEK_ROLLOVER_WEEKDAY
const WEEK_ROLLOVER_HOUR_ET = 6;
const KICKOFF_WEEKDAY = 3; // Thursday
const DRAFT_COMPLETE_MONTH = 5;

interface Ymd {
  y: number;
  m: number; // 1-12
  d: number;
}

/** Calendar day in US Eastern, shifted so the 6am rollover (not midnight) starts a new day. */
function clockToday(now: Date): Ymd {
  const shifted = new Date(now.getTime() - WEEK_ROLLOVER_HOUR_ET * 3600_000);
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", year: "numeric", month: "numeric", day: "numeric" }).formatToParts(
    shifted,
  );
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { y: get("year"), m: get("month"), d: get("day") };
}

const utcDay = ({ y, m, d }: Ymd) => Date.UTC(y, m - 1, d);
const DAY = 86400_000;
const weekday = (ms: number) => (new Date(ms).getUTCDay() + 6) % 7; // Mon=0

/** Thursday after Labor Day (first Monday of September), as a UTC day number. */
function kickoff(year: number): number {
  let ms = Date.UTC(year, 8, 1);
  while (weekday(ms) !== 0) ms += DAY;
  return ms + 3 * DAY;
}

function calendarWeek(daysSinceKickoff: number): number {
  const first = (((WEEK_ROLLOVER_WEEKDAY - KICKOFF_WEEKDAY) % 7) + 7) % 7 || 7;
  return daysSinceKickoff < first ? 1 : Math.floor((daysSinceKickoff - first) / 7) + 2;
}

export function seasonMoment(now: Date = new Date()): SeasonMoment {
  const today = clockToday(now);
  const todayMs = utcDay(today);
  const season = todayMs >= kickoff(today.y) ? today.y : today.y - 1;
  const week = calendarWeek(Math.round((todayMs - kickoff(season)) / DAY));
  if (week <= REGULAR_SEASON_WEEKS) {
    const first = FANTASY_PLAYOFF_WEEKS[0];
    const last = FANTASY_PLAYOFF_WEEKS[FANTASY_PLAYOFF_WEEKS.length - 1];
    if (week > last) return { stage: "season_end", season, week };
    if (week >= first) return { stage: "fantasy_playoffs", season, week };
    if (week === first - 1) return { stage: "playoff_push", season, week };
    return { stage: "in_season", season, week };
  }
  // After week 18: NFL postseason until Feb 20, then the offseason by calendar month.
  const postEnd = Date.UTC(season + 1, 1, 20);
  if (todayMs <= postEnd) return { stage: "nfl_postseason", season, week: null };
  const month = today.m;
  if (month >= 8) return { stage: "training_camp", season, week: null };
  if (month === 3) return { stage: "free_agency", season, week: null };
  if (month === 4) return { stage: "draft_season", season, week: null };
  if (month >= DRAFT_COMPLETE_MONTH && month <= 6) return { stage: "post_draft", season, week: null };
  if (month <= 2) return { stage: "nfl_postseason", season, week: null };
  return { stage: "training_camp", season, week: null };
}

/** Stages in which the playoff strength-of-schedule page is the timely content (weeks 9-17). */
export function playoffSosInSeason(moment: SeasonMoment): boolean {
  return moment.week !== null && moment.week >= 9 && moment.week <= FANTASY_PLAYOFF_WEEKS[FANTASY_PLAYOFF_WEEKS.length - 1];
}

/** Stages after the NFL draft when the incoming rookie class is the live question (May through the start of the season). */
export function rookieContentInSeason(moment: SeasonMoment): boolean {
  return moment.stage === "post_draft" || moment.stage === "training_camp";
}

export const PLAYOFF_SOS_PATH = "/fantasy-playoff-strength-of-schedule";
export const ROOKIE_RANKINGS_PATH = "/dynasty-rookie-rankings";
export const FANTASY_SIM_QUICKSTART_PATH = "/gm-game?quickstart=1";
export const SAMPLE_LEAGUE_PATH = "/sample-league";

export interface SeasonalLink {
  label: string;
  href: string;
}

export interface SeasonalLanding {
  stage: SeasonStage;
  eyebrow: string;
  headline: string;
  body: string;
  primary: SeasonalLink;
  secondary: SeasonalLink;
}

/** Internal CTA link with UTM tags (utm_medium=site_cta never overrides a real acquisition touch, see lib/attribution.ts). */
export function withUtm(href: string, source: string, campaign: string, content?: string): string {
  const [path, query = ""] = href.split("?");
  const params = new URLSearchParams(query);
  params.set("utm_source", source);
  params.set("utm_medium", "site_cta");
  params.set("utm_campaign", campaign);
  if (content) params.set("utm_content", content);
  return `${path}?${params.toString()}`;
}

const SIM: SeasonalLink = { label: "Play a quick Fantasy Sim game", href: FANTASY_SIM_QUICKSTART_PATH };

export function seasonalLanding(moment: SeasonMoment): SeasonalLanding {
  const { stage, week } = moment;
  switch (stage) {
    case "fantasy_playoffs":
      return {
        stage,
        eyebrow: `Fantasy playoffs, week ${week}`,
        headline: "Every start/sit call is win or go home.",
        body: "See which defenses your team and your players face through the final weeks, ranked by position.",
        primary: { label: "Playoff strength of schedule", href: PLAYOFF_SOS_PATH },
        secondary: SIM,
      };
    case "playoff_push":
      return {
        stage,
        eyebrow: "Fantasy playoffs start next week",
        headline: "Check your playoff schedule before the bracket starts.",
        body: "Weeks 15 to 17 opponents, ranked by how many points they allow to each position.",
        primary: { label: "Playoff strength of schedule", href: PLAYOFF_SOS_PATH },
        secondary: SIM,
      };
    case "in_season":
      return {
        stage,
        eyebrow: `Week ${week} of the NFL season`,
        headline: "Lineup, waiver and trade calls for this week.",
        body:
          week !== null && week >= 9
            ? "The fantasy playoffs are close. Look ahead at the schedules that decide them."
            : "Roster-aware verdicts for your league, with the reasons why.",
        primary:
          week !== null && week >= 9
            ? { label: "Playoff strength of schedule", href: PLAYOFF_SOS_PATH }
            : { label: "Free trade analyzer", href: "/trade-analyzer" },
        secondary: SIM,
      };
    case "season_end":
      return {
        stage,
        eyebrow: "The season is wrapping up",
        headline: "Start next year's dynasty roster now.",
        body: "Dynasty values reset as the offseason begins. See where every player stands.",
        primary: { label: "Dynasty rankings", href: "/dynasty-rankings/qb" },
        secondary: SIM,
      };
    case "nfl_postseason":
      return {
        stage,
        eyebrow: "Dynasty offseason",
        headline: "Rebuild or contend: price your roster honestly.",
        body: "Values keep moving all winter. Run a trade through the free analyzer before you offer it.",
        primary: { label: "Free trade analyzer", href: "/trade-analyzer" },
        secondary: SIM,
      };
    case "free_agency":
      return {
        stage,
        eyebrow: "Free agency",
        headline: "New teams change dynasty values.",
        body: "See the dynasty trade value chart and check who moved.",
        primary: { label: "Trade value chart", href: "/dynasty-trade-value-chart" },
        secondary: SIM,
      };
    case "draft_season":
      return {
        stage,
        eyebrow: "NFL Draft season",
        headline: "Scout the class before your rookie draft.",
        body: "College prospects and rookie pick values, built for dynasty.",
        primary: { label: "College scouting", href: "/college-scouting" },
        secondary: SIM,
      };
    case "post_draft":
    case "training_camp":
      return {
        stage,
        eyebrow: stage === "post_draft" ? "Rookie draft season" : "Training camp",
        headline: "The rookie class has landing spots. Rank them.",
        body: "Dynasty rookie rankings from the same value board as the rest of FantasyDesk.",
        primary: { label: "Dynasty rookie rankings", href: ROOKIE_RANKINGS_PATH },
        secondary: SIM,
      };
  }
}
