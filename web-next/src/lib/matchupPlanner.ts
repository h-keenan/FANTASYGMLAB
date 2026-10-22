/**
 * Pure helpers for the Matchup lineup planner. All scoring happens server
 * side (POST .../matchup/what-if); this only shapes lineups for the request
 * and picks which lineup the planner starts from.
 */

import type {
  MatchupResponse,
  MatchupWhatIfCandidate,
  MatchupWhatIfSlot,
  MatchupWinProbability,
} from "./api";
import type { LineupPlayer } from "./matchupPresentation";

export type PlannerSource = "suggested" | "actual";

export interface PlannerBase {
  slots: MatchupWhatIfSlot[];
  players: LineupPlayer[];
}

/** The user's lineup to start editing from: Sleeper's lineup when that tab
 * is open and posted, otherwise the suggested one. Open slots stay open. */
export function plannerBase(matchup: MatchupResponse, source: PlannerSource): PlannerBase | null {
  const mine = matchup.my_team;
  if (!mine || matchup.best_ball) return null;
  const useActual = source === "actual" && mine.has_live_data;
  const players: LineupPlayer[] = useActual ? mine.real_starters : mine.starters;
  const emptySlots = (useActual ? mine.real_empty_slots : mine.open_slots) ?? [];
  if (players.length === 0 && emptySlots.length === 0) return null;
  const slots: MatchupWhatIfSlot[] = [
    ...players.map((player) => ({ slot: player.slot || "", player_id: player.player_id })),
    ...emptySlots.map((slot) => ({ slot, player_id: null })),
  ];
  if (slots.some((entry) => !entry.slot)) return null;
  return { slots, players };
}

/** The opponent lineup the server scores against (same rule as the API). */
export function plannerOpponentPlayers(matchup: MatchupResponse): LineupPlayer[] {
  const opponent = matchup.opponent;
  if (!opponent) return [];
  return opponent.has_live_data ? opponent.real_starters : opponent.starters;
}

/** `candidate` placed at `index`; a candidate already starting elsewhere
 * trades places with the occupant (the API only offers legal trades). */
export function applySwap(
  slots: MatchupWhatIfSlot[],
  index: number,
  candidate: MatchupWhatIfCandidate,
): MatchupWhatIfSlot[] {
  const candidateId = candidate.player.player_id;
  const occupant = slots[index].player_id;
  return slots.map((entry, i) => {
    if (i === index) return { ...entry, player_id: candidateId };
    if (entry.player_id === candidateId) return { ...entry, player_id: occupant };
    return entry;
  });
}

export function emptySlotsOf(slots: MatchupWhatIfSlot[]): string[] {
  return slots.filter((entry) => !entry.player_id).map((entry) => entry.slot);
}

/** Index into `slots` for a lineup cell: a player by id, or the n-th empty
 * entry of a slot. -1 when not found. */
export function slotIndexFor(
  slots: MatchupWhatIfSlot[],
  cell: LineupPlayer | "empty" | null,
  slot: string,
  emptyOrdinal: number,
): number {
  if (cell === null) return -1;
  if (cell !== "empty") return slots.findIndex((entry) => entry.player_id === cell.player_id);
  let seen = 0;
  for (let i = 0; i < slots.length; i += 1) {
    if (!slots[i].player_id && slots[i].slot === slot) {
      if (seen === emptyOrdinal) return i;
      seen += 1;
    }
  }
  return -1;
}

export function winPercent(odds: MatchupWinProbability | null | undefined): number | null {
  return odds?.available === true && odds.probability != null ? Math.round(odds.probability * 100) : null;
}

export function sleeperLeagueUrl(leagueId: string): string {
  return `https://sleeper.com/leagues/${encodeURIComponent(leagueId)}`;
}

export function blockedLabel(reason: MatchupWhatIfCandidate["blocked_reason"]): string | null {
  if (reason === "bye") return "Bye";
  if (reason === "out") return "Out";
  if (reason === "locked") return "Locked";
  return null;
}
