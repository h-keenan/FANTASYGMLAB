// Pure presentation helpers for the Fantasy Sim draft room. Byte-identical in
// web-next/src/lib and mobile/src/lib (scripts/check_lib_twins.mjs IDENTICAL).
import { simRosterNeeds, type SimDraftPick, type SimDraftState, type SimGamePlayer, type SimGameTone, type SimPos, type SimSlot } from "./simGame";

export interface SimDraftProgress {
  round: number;
  totalRounds: number;
  /** 1-based pick inside the round. */
  pickInRound: number;
  /** Picks made so far, 0..total. */
  made: number;
  total: number;
  /** 0..1 */
  fraction: number;
}

/** Round / pick progress for the hero bar. Teams is the league size. */
export function simDraftProgress(draft: Pick<SimDraftState, "pick_no" | "total_picks" | "status">, teams: number): SimDraftProgress {
  const total = Math.max(1, draft.total_picks);
  const size = Math.max(1, teams);
  const made = draft.status === "complete" ? total : Math.min(total, Math.max(0, draft.pick_no - 1));
  const current = Math.min(total, Math.max(1, draft.pick_no));
  return {
    round: Math.floor((current - 1) / size) + 1,
    totalRounds: Math.max(1, Math.ceil(total / size)),
    pickInRound: ((current - 1) % size) + 1,
    made,
    total,
    fraction: made / total,
  };
}

/** The newest `count` picks, newest first. */
export function simDraftRecentPicks(picks: SimDraftPick[] | undefined, count = 5): SimDraftPick[] {
  return [...(picks ?? [])].sort((a, b) => b.pick_no - a.pick_no).slice(0, count);
}

/** Two-letter emblem for a team ("Dynasty Dogs" -> "DD", "Rivals" -> "RI"). */
export function simDraftTeamEmblem(name: string | null | undefined): string {
  const words = (name ?? "").replace(/\(you\)/i, "").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Short countdown copy for the hero: "Your pick" / "Next pick in 4" / "Draft complete". */
export function simDraftNextPickLabel(draft: Pick<SimDraftState, "status" | "on_the_clock" | "picks_until_you" | "your_pick_numbers" | "pick_no">): { label: string; detail: string } {
  if (draft.status === "complete") return { label: "Done", detail: "Draft complete" };
  if (draft.on_the_clock?.is_you) return { label: "Now", detail: "You are on the clock" };
  const n = draft.picks_until_you;
  const next = draft.your_pick_numbers.find((p) => p >= draft.pick_no);
  if (n > 0) return { label: `${n}`, detail: `pick${n === 1 ? "" : "s"} until yours${next ? ` (#${next})` : ""}` };
  return { label: "-", detail: "No picks left for you" };
}

/** Best (first in list order) player at each position; the list is already ADP-sorted. */
export function simDraftBestByPosition(items: SimGamePlayer[], positions: SimPos[]): { pos: SimPos; player: SimGamePlayer | null }[] {
  return positions.map((pos) => ({ pos, player: items.find((p) => p.pos === pos) ?? null }));
}

export interface SimDraftNeed {
  pos: SimPos;
  have: number;
  starters: number;
  tone: SimGameTone;
}

/** Roster needs as colored pills: empty required spot is red, partly filled is amber, filled is green, no starter slot is muted. */
export function simDraftNeedPills(roster: Pick<SimGamePlayer, "pos">[], slots: SimSlot[]): SimDraftNeed[] {
  return simRosterNeeds(roster, slots).map((n) => ({
    ...n,
    tone: n.starters === 0 ? "muted" : n.have === 0 ? "danger" : n.have < n.starters ? "warning" : "success",
  }));
}

export interface SimDraftAdpDelta {
  /** adp minus the current pick: positive means he fell past his ADP. */
  delta: number;
  label: string;
  tone: SimGameTone;
}

/**
 * Board delta against the clock: ADP 10 still there at pick 16 is a +6 steal,
 * ADP 40 at pick 16 is a -24 reach. Within 3 picks is noise (null).
 */
export function simDraftAdpDelta(adp: number | null | undefined, pickNo: number): SimDraftAdpDelta | null {
  if (adp == null || Number.isNaN(adp)) return null;
  const delta = Math.round(pickNo - adp);
  if (Math.abs(pickNo - adp) < 3) return null;
  // Taking a player whose ADP is earlier than the pick is value (steal).
  return delta > 0 ? { delta, label: `+${delta}`, tone: "success" } : { delta, label: `${delta}`, tone: "danger" };
}

export interface SimDraftChip {
  key: "out" | "bye" | "rookie";
  label: string;
  tone: SimGameTone;
}

/** Status chips worth showing in a draft row. Free agent is implied, so it never appears. */
export function simDraftRowChips(player: Pick<SimGamePlayer, "status" | "out_weeks" | "bye_week" | "age">): SimDraftChip[] {
  const chips: SimDraftChip[] = [];
  if (player.status === "out") chips.push({ key: "out", label: player.out_weeks > 0 ? `Out ${player.out_weeks}w` : "Out", tone: "danger" });
  if (player.bye_week != null && player.bye_week > 0 && player.bye_week <= 5) chips.push({ key: "bye", label: `Bye ${player.bye_week}`, tone: "warning" });
  if (player.age != null && player.age <= 21.99) chips.push({ key: "rookie", label: "Rookie", tone: "accent" });
  return chips;
}

export interface SimDraftGridCell {
  round: number;
  teamId: string;
  pickNo: number | null;
  pick: SimDraftPick | null;
}

export interface SimDraftGrid {
  teams: { team_id: string; name: string; is_you: boolean }[];
  rows: SimDraftGridCell[][];
}

/**
 * Rounds x teams grid. Columns follow the round-1 order (or the team list when
 * the order is not sent); a snake draft still lines up because cells are keyed
 * by team and round.
 */
export function simDraftBoardGrid(draft: Pick<SimDraftState, "order" | "picks" | "teams" | "total_picks">, teamCount: number): SimDraftGrid {
  const order = draft.order ?? [];
  const teamsById = new Map((draft.teams ?? []).map((t) => [t.team_id, t]));
  const columnIds: string[] = [];
  for (const slot of order) {
    if (slot.round === 1 && !columnIds.includes(slot.team_id)) columnIds.push(slot.team_id);
  }
  for (const t of draft.teams ?? []) if (!columnIds.includes(t.team_id)) columnIds.push(t.team_id);
  const teams = columnIds.map((id) => ({ team_id: id, name: teamsById.get(id)?.name ?? "Team", is_you: Boolean(teamsById.get(id)?.is_you) }));
  const rounds = Math.max(1, Math.ceil(draft.total_picks / Math.max(1, teamCount)));
  const pickAt = new Map<string, SimDraftPick>();
  for (const pk of draft.picks ?? []) pickAt.set(`${pk.round}:${pk.team_id}`, pk);
  const pickNoAt = new Map<string, number>();
  for (const slot of order) pickNoAt.set(`${slot.round}:${slot.team_id}`, slot.pick_no);
  const rows: SimDraftGridCell[][] = [];
  for (let round = 1; round <= rounds; round += 1) {
    rows.push(
      teams.map((t) => {
        const key = `${round}:${t.team_id}`;
        const pick = pickAt.get(key) ?? null;
        return { round, teamId: t.team_id, pickNo: pick?.pick_no ?? pickNoAt.get(key) ?? null, pick };
      }),
    );
  }
  return { teams, rows };
}
