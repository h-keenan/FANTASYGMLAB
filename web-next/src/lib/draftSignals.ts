// View-model helpers for the Draft Center signal rows (web + mobile twins).
// The API (modules/draft_center_cards.py, card schema 2) returns structured
// `rows` beside the legacy `items` strings; clients render rows and fall back
// to the strings only when a response predates schema 2.

export type DraftSignalEvidence = { key: string; label: string; value: string };

export type DraftSignalRow = {
  team_id: string;
  team_name: string;
  avatar_url: string | null;
  /** Normalized strategy key: contender, fringe_contender, retool, rebuild, tank. */
  strategy: string;
  strategy_display: string;
  draft_rank: number | null;
  draft_rank_tied: boolean;
  future_rank: number | null;
  future_rank_tied: boolean;
  firsts: number;
  reason_code: string;
  /** One line, 60 characters at most. */
  reason_short: string;
  /** The full sentence: shown only in the detail sheet. */
  reason_long: string;
  evidence: DraftSignalEvidence[];
};

export type SignalTone = "success" | "warning" | "accent" | "neutral";

/** Rows shown before "See all". */
export const SIGNAL_TOP_N = 3;

/** Colour family for the status chip: the team's direction. */
export function strategyTone(strategy: string): SignalTone {
  const key = (strategy || "").toLowerCase();
  if (key === "contender" || key === "fringe_contender") return "success";
  if (key === "retool") return "warning";
  if (key === "rebuild" || key === "tank") return "accent";
  return "neutral";
}

function rankLabel(rank: number, tied: boolean): string {
  return `${tied ? "T-" : ""}#${rank}`;
}

/**
 * The metric pills for a row: "Draft #10" and "Future #10", collapsed into one
 * "Picks #10" when both ranks are equal (the old string showed the same number
 * twice). Missing ranks are skipped, never shown as a dash.
 */
export function signalPills(row: Pick<DraftSignalRow, "draft_rank" | "draft_rank_tied" | "future_rank" | "future_rank_tied">): { key: string; label: string }[] {
  const { draft_rank: draft, future_rank: future } = row;
  if (draft != null && future != null && draft === future && row.draft_rank_tied === row.future_rank_tied) {
    return [{ key: "picks", label: `Picks ${rankLabel(draft, row.draft_rank_tied)}` }];
  }
  const pills: { key: string; label: string }[] = [];
  if (draft != null) pills.push({ key: "draft", label: `Draft ${rankLabel(draft, row.draft_rank_tied)}` });
  if (future != null) pills.push({ key: "future", label: `Future ${rankLabel(future, row.future_rank_tied)}` });
  return pills;
}

/** Rows to show: the top few, or all of them once expanded. */
export function visibleSignalRows<T>(rows: readonly T[], expanded: boolean, top: number = SIGNAL_TOP_N): T[] {
  return expanded ? [...rows] : rows.slice(0, top);
}

export function seeAllLabel(total: number, top: number = SIGNAL_TOP_N): string | null {
  return total > top ? `See all (${total})` : null;
}

/** One spoken line for the row button. */
export function signalSpokenLabel(row: DraftSignalRow): string {
  const pills = signalPills(row).map((pill) => pill.label);
  return [row.team_name, ...pills, row.strategy_display, row.reason_short].filter(Boolean).join(", ");
}

/** The structured rows of a card, or null when the response is a legacy (pre-schema-2) one. */
export function cardRows(card: { rows?: DraftSignalRow[] | null }): DraftSignalRow[] | null {
  return Array.isArray(card.rows) && card.rows.length > 0 ? card.rows : null;
}
