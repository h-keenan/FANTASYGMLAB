import type { SaveLeagueResponse } from "@/lib/api";

/** Honest copy for the saved-league cap (modules/saved_leagues.py). */
export const LEAGUE_CAP_UPSELL = {
  title: "Add more leagues with Pro",
  body: "Free includes 1 league. Pro supports up to 5.",
};

/** Messages for every non-cap refusal reason POST /v1/leagues/save returns. */
const SAVE_FAILURE_COPY: Record<string, string> = {
  league_not_found: "That league didn't load just now. Please try again.",
  espn_team_not_selected: "Pick which team is yours first.",
  mapping_too_low: "Too few of this league's players matched FantasyDesk's player list to value it accurately.",
};

export function saveFailureMessage(reason: string | undefined): string {
  return (reason && SAVE_FAILURE_COPY[reason]) || "Could not save that league right now. Please try again in a moment.";
}

/** A save only counts when the server said ok. A failed save must never open the league. */
export function isSaveFailure(saved: SaveLeagueResponse | null | undefined): boolean {
  return !saved || saved.ok !== true;
}
