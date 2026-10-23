import type { ThisWeek, ThisWeekRow } from "@/lib/api";

type RowRoute = NonNullable<ThisWeekRow["route"]>;
type NextRoute = NonNullable<ThisWeek["next_action"]>["route"];

const PATH: Record<Exclude<RowRoute | NextRoute, "connect_league">, string> = {
  matchup: "matchup",
  waivers: "waivers",
  trade_hub: "trade-hub",
  draft_center: "draft-center",
  live_draft: "live-draft",
};

/** Internal href for a "This week" CTA. Matchup is where lineups are reviewed
 * (we can't change a Sleeper lineup). Only Waivers and Trade Hub read `playerId`. */
export function thisWeekHref(route: RowRoute | NextRoute, leagueId: string, leagueName: string, playerId = ""): string {
  if (route === "connect_league") return "/connect-league";
  const params = new URLSearchParams({ name: leagueName });
  if (playerId && (route === "waivers" || route === "trade_hub")) params.set("playerId", playerId);
  return `/${PATH[route]}/${encodeURIComponent(leagueId)}?${params.toString()}`;
}

const TONE_COLOR: Record<ThisWeekRow["tone"], string> = {
  positive: "var(--color-success)",
  risk: "var(--color-danger)",
  waiver: "var(--color-accent)",
  trade: "var(--color-accent)",
  neutral: "var(--color-text-muted)",
};

export function thisWeekToneColor(tone: ThisWeekRow["tone"]): string {
  return TONE_COLOR[tone] ?? TONE_COLOR.neutral;
}
