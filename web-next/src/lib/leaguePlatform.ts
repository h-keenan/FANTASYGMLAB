/**
 * Which platform a saved league comes from, and which pages it can open.
 *
 * ESPN leagues are saved under the id "espn:{espnLeagueId}:{season}"
 * (modules/espn_leagues.py on the API side), so the id itself carries the
 * platform marker. They can feed only the pages listed in
 * ESPN_SUPPORTED_SEGMENTS; every other league-scoped page shows
 * "Not available for ESPN leagues yet" (EspnUnavailableState) instead of
 * loading, and the API refuses those routes for ESPN ids too.
 */

export const ESPN_NOT_AVAILABLE_MESSAGE = "Not available for ESPN leagues yet.";

/**
 * Fleaflicker ("fleaflicker:{id}:{season}") and MFL ("mfl:{id}:{season}")
 * leagues (modules/fleaflicker_leagues.py, modules/mfl_leagues.py) follow the
 * exact ESPN pattern: same saved-league column, same Sleeper-shaped data, same
 * supported pages. So `isEspnLeagueId` (kept under its old name for its many
 * callers) is true for every imported, non-Sleeper league.
 */
const IMPORTED_PLATFORM_LABELS: Record<string, string> = { espn: "ESPN", fleaflicker: "Fleaflicker", mfl: "MFL" };

/** "ESPN" | "Fleaflicker" | "MFL" for an imported league id, "" for Sleeper. */
export function importedPlatformLabel(leagueId: string | null | undefined): string {
  if (typeof leagueId !== "string") return "";
  const prefix = leagueId.split(":", 1)[0];
  return leagueId.includes(":") ? (IMPORTED_PLATFORM_LABELS[prefix] ?? "") : "";
}

export function isEspnLeagueId(leagueId: string | null | undefined): boolean {
  return importedPlatformLabel(leagueId) !== "";
}

/** "Not available for MFL leagues yet." for the league's own platform. */
export function notAvailableMessage(leagueId: string | null | undefined): string {
  return `Not available for ${importedPlatformLabel(leagueId) || "ESPN"} leagues yet.`;
}

/** First path segment of every league-scoped page an ESPN league can open. */
export const ESPN_SUPPORTED_SEGMENTS = new Set(["my-team", "trade-analyzer", "players", "player-compare", "league-rankings"]);

/** First path segment of every page that takes a league id as its second segment. */
const LEAGUE_SCOPED_SEGMENTS = new Set([
  "dashboard",
  "alerts",
  "my-team",
  "matchup",
  "waivers",
  "players",
  "player-compare",
  "league-rankings",
  "trade-hub",
  "trade-finder",
  "trade-analyzer",
  "gm-plan",
  "gm-targets",
  "team-situation",
  "draft-center",
  "live-draft",
  "league-recaps",
  "guess-the-player-leaderboard",
]);

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The ESPN league id when `pathname` is a page ESPN leagues can't open yet, else null. */
export function espnUnavailableLeagueId(pathname: string | null | undefined): string | null {
  if (!pathname) return null;
  const [, segment = "", rawLeagueId = ""] = pathname.split("/");
  if (!LEAGUE_SCOPED_SEGMENTS.has(segment) || ESPN_SUPPORTED_SEGMENTS.has(segment)) return null;
  const leagueId = safeDecode(rawLeagueId);
  return isEspnLeagueId(leagueId) ? leagueId : null;
}

/** Where opening a league lands: Dashboard for Sleeper, My Team for ESPN
 * (ESPN leagues have no Dashboard yet). */
export function leagueHomePath(leagueId: string, leagueName: string): string {
  const page = isEspnLeagueId(leagueId) ? "my-team" : "dashboard";
  return `/${page}/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`;
}

/** Seasons offered in the ESPN import's season picker, newest first. */
export function espnSeasonOptions(now: Date = new Date()): number[] {
  const year = now.getFullYear();
  return [year, year - 1, year - 2];
}

/** ESPN setting a league manager changes to make a private league readable. */
export const ESPN_PRIVATE_LEAGUE_HINT =
  "This league is private. Ask your league manager to turn on League Settings > Make League Viewable to Public in ESPN, then retry.";

/** Privacy-safe analytics `result` for a failed ESPN import preview. */
export function espnImportFailureResult(reason: string | null | undefined): "espn_private" | "espn_not_found" | "espn_error" {
  if (reason === "private_league") return "espn_private";
  if (reason === "league_not_found") return "espn_not_found";
  return "espn_error";
}
