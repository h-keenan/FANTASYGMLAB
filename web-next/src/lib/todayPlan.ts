import type { BriefingItem, ThisWeek, ThisWeekRow } from "@/lib/api";
import { thisWeekTradeIdeaHeadline } from "@/lib/thisWeek";

/**
 * The merged Dashboard "Today" hero (formerly the separate "This week" strip
 * and "Today" game-plan list). One schedule-aware ordering:
 *
 * - NFL lineups lock Thursday through Monday, so every day except Tuesday and
 *   Wednesday the lineup row is "today"; waivers clear Tuesday and Wednesday,
 *   so the waiver row is "today" then and "later this week" otherwise. A risk
 *   lineup row (an out starter) is always today. The trade row is never
 *   time-critical.
 * - Server top-priority items are always today; they sit after a risk lineup
 *   row and ahead of ordinary rows.
 * - Items that appeared in both lists are shown once.
 *
 * Pure. Mirrored in mobile/src/lib/todayPlan.ts (keep the two in sync).
 */

export type TodayEntry = { kind: "row"; row: ThisWeekRow } | { kind: "card"; item: BriefingItem };

export interface TodayPlan {
  nextAction: ThisWeek["next_action"];
  /** Most urgent first. */
  today: TodayEntry[];
  /** Rest-of-week rows. */
  later: ThisWeekRow[];
  /** Duplicates removed from the display. */
  dropped: { rows: ThisWeekRow[]; items: BriefingItem[] };
  isEmpty: boolean;
}

/** Tuesday (2) and Wednesday (3): the week's games are over and waivers clear. */
export function isWaiverDay(now: Date): boolean {
  const day = now.getDay();
  return day === 2 || day === 3;
}

function rowIsToday(row: ThisWeekRow, now: Date): boolean {
  if (row.key === "lineup") return row.tone === "risk" || !isWaiverDay(now);
  if (row.key === "waiver") return isWaiverDay(now);
  return false;
}

export function buildTodayPlan(
  thisWeek: ThisWeek | null | undefined,
  items: BriefingItem[],
  now: Date = new Date(),
): TodayPlan {
  const rows = thisWeek?.rows ?? [];
  const nextAction = thisWeek?.next_action ?? null;
  const tradeHeadline = thisWeekTradeIdeaHeadline(thisWeek);
  const topAll = items.filter((item) => item.category === "top_priority");

  // A top-priority trade card the trade row already shows is dropped; a
  // waiver row for the same player a waiver card already covers is dropped
  // (the card carries more context and links to the same place).
  const cards = topAll.filter((item) => !(tradeHeadline && (item.headline ?? "").trim() === tradeHeadline));
  const droppedItems = topAll.filter((item) => !cards.includes(item));
  const cardWaiverIds = new Set(
    cards.filter((item) => item.destination === "waivers" && item.route_player_id).map((item) => item.route_player_id),
  );
  const droppedRows = rows.filter((row) => row.key === "waiver" && row.player_id && cardWaiverIds.has(row.player_id));
  const keptRows = rows.filter((row) => !droppedRows.includes(row));

  const todayRows = keptRows.filter((row) => rowIsToday(row, now));
  const later = keptRows.filter((row) => !rowIsToday(row, now));
  const urgent = todayRows.filter((row) => row.tone === "risk");
  const ordinary = todayRows.filter((row) => row.tone !== "risk");

  const today: TodayEntry[] = [
    ...urgent.map((row): TodayEntry => ({ kind: "row", row })),
    ...cards.map((item): TodayEntry => ({ kind: "card", item })),
    ...ordinary.map((row): TodayEntry => ({ kind: "row", row })),
  ];
  return {
    nextAction,
    today,
    later,
    dropped: { rows: droppedRows, items: droppedItems },
    isEmpty: !nextAction && today.length === 0 && later.length === 0,
  };
}

/** Section title: "Today", with the week when the server knows it. */
export function todayTitle(thisWeek: ThisWeek | null | undefined): string {
  return thisWeek?.week ? `Today · Week ${thisWeek.week}` : "Today";
}
