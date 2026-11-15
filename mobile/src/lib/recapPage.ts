/**
 * The weekly recap page model (docs/ui-patterns.md, "Weekly recap page"): the page is a status header (the week's
 * result) over a short stack of compact modules, one per kind of story, each collapsed to a dense summary line and
 * expanding to the full stories. Everything here is derived from the recap payload the API already returns
 * (`GET /v1/leagues/{id}/recap`); nothing is invented. Pure and import-free; byte-identical twin of
 * mobile/src/lib/recapPage.ts.
 */

export interface RecapPlayerAsset {
  kind: "player" | "pick";
  name: string;
  player_id?: string;
  position?: string;
  team?: string;
  label?: string;
  season?: string;
  round?: number;
}

export interface RecapSideInput {
  team_name: string;
  roster_id: string;
  assets?: RecapPlayerAsset[];
}

export interface RecapStoryInput {
  story_type: string;
  title: string;
  summary: string;
  primary_team: string;
  secondary_team: string;
  primary_roster_id: string;
  secondary_roster_id: string;
  players: string[];
  metric_label: string;
  metric_value: string;
  history_filter?: string;
  editorial_label?: string;
  sides?: RecapSideInput[];
  left_assets?: RecapPlayerAsset[];
  right_assets?: RecapPlayerAsset[];
  winner_points?: number;
  loser_points?: number;
  player_assets?: RecapPlayerAsset[];
}

export interface RecapInput {
  week: number;
  season?: string;
  headline: string;
  stories: RecapStoryInput[];
  incomplete: boolean;
}

export type RecapTone = "success" | "danger" | "warning" | "accent" | "muted";
export type RecapSectionKey = "scoring" | "matchups" | "waivers" | "trades" | "activity" | "roster" | "other";

export interface RecapPart {
  key: string;
  text: string;
  tone?: "success" | "danger" | "warning" | "accent" | "muted" | "action";
  strong?: boolean;
}

export interface RecapSection {
  key: RecapSectionKey;
  title: string;
  stories: RecapStoryInput[];
  /** The collapsed summary line: the key numbers, in order. */
  parts: RecapPart[];
}

export interface RecapHeroStat {
  key: string;
  label: string;
  value: string;
  tone?: RecapTone;
}

export interface RecapHero {
  kicker: string;
  headline: string;
  context: string | null;
  ring: { pct: null; center: string; label: string; tone: "accent" };
  stats: RecapHeroStat[];
  /** The week's scoring leader (the one champion highlight), when the week has one. */
  leader: { team: string; rosterId: string; points: string } | null;
}

export interface RecapPage {
  hero: RecapHero;
  sections: RecapSection[];
}

const SECTION_ORDER: RecapSectionKey[] = ["scoring", "matchups", "waivers", "trades", "activity", "roster", "other"];

export const RECAP_SECTION_TITLES: Record<RecapSectionKey, string> = {
  scoring: "Scoring",
  matchups: "Matchups",
  waivers: "Waivers",
  trades: "Trades",
  activity: "League activity",
  roster: "Roster watch",
  other: "More storylines",
};

export function recapSectionKey(storyType: string): RecapSectionKey {
  if (storyType.startsWith("performance")) return "scoring";
  if (storyType.startsWith("matchup")) return "matchups";
  if (storyType.startsWith("waiver")) return "waivers";
  if (storyType === "trade") return "trades";
  if (storyType.startsWith("activity")) return "activity";
  if (storyType === "roster_riser") return "roster";
  return "other";
}

const has = (v: string | undefined | null): v is string => Boolean(v && v.trim());

function find(stories: RecapStoryInput[], type: string): RecapStoryInput | undefined {
  return stories.find((s) => s.story_type === type);
}

/** "183.4" -> "183.4"; a FAAB "$14" stays "$14". Empty stays empty (never zero-filled). */
export function recapMetric(story: RecapStoryInput): string {
  return has(story.metric_value) ? story.metric_value.trim() : "";
}

export function isMatchupStory(story: RecapStoryInput): boolean {
  return story.story_type === "matchup" || story.story_type === "matchup_close";
}

/** "183.4 to 120.2" scoreline for a matchup story, from the recorded points (older payloads: null). */
export function recapScoreline(story: RecapStoryInput): { winner: string; loser: string } | null {
  if (typeof story.winner_points !== "number" || typeof story.loser_points !== "number") return null;
  return { winner: story.winner_points.toFixed(1), loser: story.loser_points.toFixed(1) };
}

/** The sentence the module summary and the hero use for a story, short enough for one line on a phone. */
function storyLine(story: RecapStoryInput): string {
  const metric = recapMetric(story);
  switch (story.story_type) {
    case "performance":
      return `Top ${metric} ${story.primary_team}`;
    case "performance_low":
      return `Low ${metric} ${story.primary_team}`;
    case "matchup":
      return `Biggest margin ${metric}`;
    case "matchup_close":
      return `Closest ${metric}`;
    case "waiver":
      return `${metric} ${story.players[0] ?? story.primary_team}`.trim();
    case "waiver_low":
      return `Cheapest ${metric} ${story.players[0] ?? story.primary_team}`.trim();
    case "trade":
      return story.sides && story.sides.length > 2 ? `${story.sides.length}-team trade` : `${story.primary_team} and ${story.secondary_team}`;
    case "activity":
      return `${story.primary_team} ${metric} moves`.trim();
    case "activity_low":
      return `Quietest ${story.primary_team}`;
    case "roster_riser":
      return `${story.primary_team} ${metric}`.trim();
    default:
      return story.title;
  }
}

function toneFor(story: RecapStoryInput): RecapPart["tone"] {
  if (story.story_type === "waiver" || story.story_type === "waiver_low") return "success";
  if (story.story_type === "performance") return "success";
  if (story.story_type === "performance_low") return "muted";
  return undefined;
}

export function recapSectionParts(stories: RecapStoryInput[]): RecapPart[] {
  const parts: RecapPart[] = stories.map((story, i) => ({ key: `${story.story_type}-${i}`, text: storyLine(story).trim(), tone: toneFor(story), strong: i === 0 }));
  return parts.filter((p) => p.text);
}

/** Is this roster one of the teams the story is about? */
export function storyInvolves(story: RecapStoryInput, rosterId: string): boolean {
  if (!rosterId) return false;
  if (story.primary_roster_id === rosterId || story.secondary_roster_id === rosterId) return true;
  return Boolean(story.sides?.some((s) => s.roster_id === rosterId));
}

/** One honest line about the signed-in team this week, from the stories that name it; null when none do. */
export function recapYourLine(stories: RecapStoryInput[], myRosterId: string): string | null {
  if (!myRosterId) return null;
  const mine = stories.filter((s) => storyInvolves(s, myRosterId));
  if (mine.length === 0) return null;
  const lines: string[] = [];
  for (const story of mine) {
    const scoreline = recapScoreline(story);
    const score = scoreline ? ` ${scoreline.winner} to ${scoreline.loser}` : "";
    if (story.story_type === "performance" && story.primary_roster_id === myRosterId) lines.push(`You had the week's top score, ${recapMetric(story)}`);
    else if (story.story_type === "performance_low" && story.primary_roster_id === myRosterId) lines.push(`You had the week's lowest score, ${recapMetric(story)}`);
    else if (isMatchupStory(story)) {
      const won = story.primary_roster_id === myRosterId;
      lines.push(won ? `You beat ${story.secondary_team}${score}` : `You lost to ${story.primary_team}${score}`);
    } else if (story.story_type === "trade") lines.push("You were in the week's trade");
    else if (story.story_type === "waiver" || story.story_type === "waiver_low") lines.push(`You added ${story.players[0] ?? "a player"} ${recapMetric(story)}`.trim());
    else if (story.story_type === "activity" && story.primary_roster_id === myRosterId) lines.push(`You made the most moves, ${recapMetric(story)}`);
  }
  return lines.length ? lines.slice(0, 2).join(". ") : null;
}

export function buildRecapPage(recap: RecapInput, myRosterId: string = ""): RecapPage {
  const stories = recap.stories ?? [];
  const leaderStory = find(stories, "performance");
  const lowStory = find(stories, "performance_low");
  const closeStory = find(stories, "matchup_close");
  const bigStory = find(stories, "matchup");
  const stats: RecapHeroStat[] = [];
  if (leaderStory && recapMetric(leaderStory)) stats.push({ key: "top", label: "Top score", value: recapMetric(leaderStory), tone: "success" });
  if (lowStory && recapMetric(lowStory)) stats.push({ key: "low", label: "Low score", value: recapMetric(lowStory), tone: "danger" });
  const margin = closeStory ?? bigStory;
  if (margin && recapMetric(margin)) stats.push({ key: "margin", label: closeStory ? "Closest game" : "Top margin", value: recapMetric(margin) });
  const headline = leaderStory && recapMetric(leaderStory) ? `${leaderStory.primary_team} led the week with ${recapMetric(leaderStory)}` : recap.headline;
  const hero: RecapHero = {
    kicker: `Week ${recap.week} recap`,
    headline,
    context: recapYourLine(stories, myRosterId),
    ring: { pct: null, center: `W${recap.week}`, label: `Week ${recap.week}`, tone: "accent" },
    stats: stats.slice(0, 3),
    leader: leaderStory && recapMetric(leaderStory) ? { team: leaderStory.primary_team, rosterId: leaderStory.primary_roster_id, points: recapMetric(leaderStory) } : null,
  };
  const sections: RecapSection[] = [];
  for (const key of SECTION_ORDER) {
    const inSection = stories.filter((s) => recapSectionKey(s.story_type) === key);
    if (inSection.length === 0) continue;
    sections.push({ key, title: RECAP_SECTION_TITLES[key], stories: inSection, parts: recapSectionParts(inSection) });
  }
  return { hero, sections };
}

/** Week chips for the one week strip, newest first: every completed week, nothing folded away. */
export function recapWeekChips(maxCompletedWeek: number): { label: string; value: string }[] {
  const out: { label: string; value: string }[] = [];
  for (let week = Math.max(0, Math.floor(maxCompletedWeek)); week >= 1; week -= 1) out.push({ label: `Wk ${week}`, value: String(week) });
  return out;
}

/** FAAB amount in dollars from a story metric ("$14" -> 14); null when it is not one. */
export function recapFaab(story: RecapStoryInput): number | null {
  const m = /^\$?\s*(\d+)/.exec(story.metric_value ?? "");
  return m ? Number(m[1]) : null;
}
