/**
 * Slot-by-slot lineup comparison logic for the Matchup screen: leader per
 * slot, a mini win-bar share, the slots that decide the matchup, and totals
 * (current and projected final). Pure; byte-identical twin of
 * mobile/src/lib/lineupSlots.ts.
 */

import { playerCardFromStarter, type PlayerCardModel } from "./playerCard";
import { slotDisplayLabel, type LineupComparisonRow, type LineupPlayer } from "./matchupPresentation";

export type SlotLeader = "mine" | "opponent" | "tie" | null;
export type SlotCell = { kind: "player"; card: PlayerCardModel; source: LineupPlayer } | { kind: "empty" } | { kind: "none" };

export interface SlotComparison {
  key: string;
  /** Index of the row in the unsorted comparison (planner slot lookups). */
  index: number;
  /** Raw slot name (QB, RB, FLEX, ...). */
  slot: string;
  /** Numbered when the lineup has several of a kind: RB1, RB2, W/R. */
  label: string;
  row: LineupComparisonRow;
  mine: SlotCell;
  opponent: SlotCell;
  /** Current points (real once started, else the projection). */
  myNow: number | null;
  opponentNow: number | null;
  myFinal: number | null;
  opponentFinal: number | null;
  /** Who leads the slot right now. */
  leader: SlotLeader;
  /** Absolute current gap. */
  margin: number;
  /** Absolute projected-final gap (falls back to the current gap). */
  finalMargin: number;
  /** Projected points still to come from both players. */
  remaining: number;
  /** My share (0-100) of this slot's projected final, for the mini win bar; null when unknown. */
  barShare: number | null;
  /** True when this slot is among those that will decide the matchup. */
  decides: boolean;
  /** Either player is on bye or ruled out. */
  mineUnavailable: boolean;
  opponentUnavailable: boolean;
}

export type SlotSortMode = "lineup" | "decisive";

function cellOf(player: LineupPlayer | "empty" | null): SlotCell {
  if (player === null) return { kind: "none" };
  if (player === "empty") return { kind: "empty" };
  return { kind: "player", card: playerCardFromStarter(player), source: player };
}

/** What the player has right now: real points once his game started, else his projection (0 on bye). */
export function cardNowPoints(card: PlayerCardModel): number | null {
  if (card.bye) return 0;
  if (card.points != null) return card.points;
  return card.projection;
}

function earnedOf(cell: SlotCell): number {
  return cell.kind === "player" && !cell.card.bye ? (cell.card.points ?? 0) : 0;
}

function nowOf(cell: SlotCell): number | null {
  return cell.kind === "player" ? cardNowPoints(cell.card) : cell.kind === "empty" ? 0 : null;
}

function finalOf(cell: SlotCell): number | null {
  if (cell.kind === "player") return cell.card.expectedFinal ?? cardNowPoints(cell.card);
  return cell.kind === "empty" ? 0 : null;
}

function leaderOf(a: number | null, b: number | null): SlotLeader {
  if (a == null || b == null) return null;
  const diff = Math.round((a - b) * 10) / 10;
  return diff > 0 ? "mine" : diff < 0 ? "opponent" : "tie";
}

function unavailable(cell: SlotCell): boolean {
  return cell.kind === "player" && (cell.card.bye || cell.card.out);
}

/** Numbered labels per slot name: a lone slot keeps its plain label, several become RB1, RB2, ... */
export function numberedSlotLabels(slots: string[]): string[] {
  const total = new Map<string, number>();
  for (const slot of slots) total.set(slot, (total.get(slot) ?? 0) + 1);
  const seen = new Map<string, number>();
  return slots.map((slot) => {
    const base = slotDisplayLabel(slot);
    if ((total.get(slot) ?? 0) <= 1) return base;
    const index = (seen.get(slot) ?? 0) + 1;
    seen.set(slot, index);
    return `${base}${index}`;
  });
}

/** How many slots to flag as "deciding": the closest still-open ones. */
export const DECIDING_SLOT_COUNT = 2;
/** A slot with less than this many projected points to come is treated as settled. */
export const SETTLED_REMAINING = 1;

export function compareLineupSlots(rows: LineupComparisonRow[]): SlotComparison[] {
  const labels = numberedSlotLabels(rows.map((row) => row.slot));
  const slots: SlotComparison[] = rows.map((row, index) => {
    const mine = cellOf(row.mine);
    const opponent = cellOf(row.opponent);
    const myNow = nowOf(mine);
    const opponentNow = nowOf(opponent);
    const myFinal = finalOf(mine);
    const opponentFinal = finalOf(opponent);
    const remaining =
      Math.max(0, (myFinal ?? 0) - earnedOf(mine)) + Math.max(0, (opponentFinal ?? 0) - earnedOf(opponent));
    const a = myFinal ?? myNow;
    const b = opponentFinal ?? opponentNow;
    const total = a != null && b != null ? Math.max(0, a) + Math.max(0, b) : 0;
    return {
      key: `${row.slot}-${index}`,
      index,
      slot: row.slot,
      label: labels[index],
      row,
      mine,
      opponent,
      myNow,
      opponentNow,
      myFinal,
      opponentFinal,
      leader: leaderOf(myNow, opponentNow),
      margin: myNow != null && opponentNow != null ? Math.abs(myNow - opponentNow) : 0,
      finalMargin: a != null && b != null ? Math.abs(a - b) : 0,
      remaining,
      barShare: a != null && b != null && total > 0 ? (Math.max(0, a) / total) * 100 : null,
      decides: false,
      mineUnavailable: unavailable(mine),
      opponentUnavailable: unavailable(opponent),
    };
  });
  // Deciding slots: still open (points left to come, or not yet played) and
  // closest on projected final; more projection left breaks ties.
  const open = slots
    .filter((slot) => slot.remaining >= SETTLED_REMAINING && slot.myFinal != null && slot.opponentFinal != null)
    .sort((x, y) => x.finalMargin - y.finalMargin || y.remaining - x.remaining);
  for (const slot of open.slice(0, DECIDING_SLOT_COUNT)) slot.decides = true;
  return slots;
}

export function sortSlots(slots: SlotComparison[], mode: SlotSortMode): SlotComparison[] {
  if (mode === "lineup") return slots;
  return slots
    .map((slot, index) => ({ slot, index }))
    .sort((x, y) => Number(y.slot.decides) - Number(x.slot.decides) || x.index - y.index)
    .map((entry) => entry.slot);
}

export interface SlotTotals {
  mineNow: number;
  opponentNow: number;
  mineFinal: number;
  opponentFinal: number;
  marginNow: number;
  marginFinal: number;
}

export function slotTotals(slots: SlotComparison[]): SlotTotals {
  let mineNow = 0;
  let opponentNow = 0;
  let mineFinal = 0;
  let opponentFinal = 0;
  for (const slot of slots) {
    mineNow += slot.myNow ?? 0;
    opponentNow += slot.opponentNow ?? 0;
    mineFinal += slot.myFinal ?? slot.myNow ?? 0;
    opponentFinal += slot.opponentFinal ?? slot.opponentNow ?? 0;
  }
  return { mineNow, opponentNow, mineFinal, opponentFinal, marginNow: mineNow - opponentNow, marginFinal: mineFinal - opponentFinal };
}

/** Player ids whose live points changed between two payloads' slot lists (drives the row pulse). */
export function changedPlayerIds(previous: SlotComparison[] | null, next: SlotComparison[]): Set<string> {
  const changed = new Set<string>();
  if (!previous) return changed;
  const before = new Map<string, number | null>();
  for (const slot of previous) {
    for (const cell of [slot.mine, slot.opponent]) {
      if (cell.kind === "player" && cell.card.playerId) before.set(cell.card.playerId, cell.card.points);
    }
  }
  for (const slot of next) {
    for (const cell of [slot.mine, slot.opponent]) {
      if (cell.kind !== "player" || !cell.card.playerId) continue;
      const old = before.get(cell.card.playerId);
      if (old !== undefined && cell.card.points != null && old !== cell.card.points) changed.add(cell.card.playerId);
    }
  }
  return changed;
}
