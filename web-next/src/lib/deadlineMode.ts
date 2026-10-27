/**
 * Deadline mode: one league-calendar notion shared by web and the app. The
 * block between the SHARED markers is byte-identical to
 * mobile/src/lib/deadlineMode.ts (a mobile test compares them): edit both
 * together. Pure TS, no imports, so node --test can run it.
 *
 * Sleeper exposes the trade deadline as a WEEK, never a date, so every count
 * here is in whole weeks derived from the league's real current week. Nothing
 * is guessed: no deadline, an unknown week, or an offseason league yields
 * state "none".
 */

// SHARED BEGIN
export interface DeadlineWindow {
  trade_deadline_week: number | null;
  current_week: number | null;
  trade_deadline_passed: boolean;
}

/** The dashboard card (and push) wake up this many weeks before the deadline. */
export const DEADLINE_CARD_WEEKS = 2;

export type DeadlineState =
  | { phase: "none" }
  | { phase: "closed" }
  | { phase: "open"; deadlineWeek: number; weeksLeft: number | null };

export function deadlineState(window: DeadlineWindow | null | undefined): DeadlineState {
  if (!window) return { phase: "none" };
  if (window.trade_deadline_passed) return { phase: "closed" };
  const deadlineWeek = window.trade_deadline_week;
  if (deadlineWeek === null || deadlineWeek === undefined) return { phase: "none" };
  const current = window.current_week;
  const weeksLeft = current !== null && current !== undefined && current <= deadlineWeek ? deadlineWeek - current : null;
  return { phase: "open", deadlineWeek, weeksLeft };
}

/** How a team should approach the deadline. */
export type DeadlinePosture = "buy" | "sell" | "balanced";

/**
 * Posture from the effective team strategy (modules.team_eval keys:
 * contender / fringe_contender / retool / rebuild / tank). Competing teams
 * buy, rebuilding teams sell, everything else (including an unset stance,
 * which the server maps to retool) stays balanced.
 */
export function deadlinePosture(strategy: string | null | undefined): DeadlinePosture {
  const key = String(strategy ?? "").trim().toLowerCase();
  if (key === "contender" || key === "fringe_contender") return "buy";
  if (key === "rebuild" || key === "tank") return "sell";
  return "balanced";
}

export interface DeadlineCopy {
  /** "Deadline in 2 weeks: buy a starter" */
  headline: string;
  /** One sentence on why, for the posture. */
  body: string;
  /** True in the deadline week itself ("last call"). */
  urgent: boolean;
}

const POSTURE_ACTION: Record<DeadlinePosture, string> = {
  buy: "buy a starter",
  sell: "sell aging depth",
  balanced: "review your trade ideas",
};

const POSTURE_BODY: Record<DeadlinePosture, string> = {
  buy: "You are competing, so upgrade a starting spot while sellers still have time to deal.",
  sell: "Veterans whose value is about to fall bring the most now. Aim for picks and younger players.",
  balanced: "Check which of your players are worth more to another team than to yours.",
};

export function deadlineWhen(weeksLeft: number | null, deadlineWeek: number): string {
  if (weeksLeft === null) return `Deadline is Week ${deadlineWeek}`;
  if (weeksLeft === 0) return "Last call, deadline is this week";
  return `Deadline in ${weeksLeft} week${weeksLeft === 1 ? "" : "s"}`;
}

/** Null unless a real deadline is still ahead. */
export function deadlineCopy(state: DeadlineState, posture: DeadlinePosture): DeadlineCopy | null {
  if (state.phase !== "open") return null;
  return {
    headline: `${deadlineWhen(state.weeksLeft, state.deadlineWeek)}: ${POSTURE_ACTION[posture]}`,
    body: POSTURE_BODY[posture],
    urgent: state.weeksLeft === 0,
  };
}

/** The Dashboard countdown card shows only in the last DEADLINE_CARD_WEEKS weeks. */
export function showDeadlineCard(state: DeadlineState): boolean {
  return state.phase === "open" && state.weeksLeft !== null && state.weeksLeft <= DEADLINE_CARD_WEEKS;
}

export const DEADLINE_CLOSED_COPY = "The trade deadline has passed. Trades are closed until the offseason.";
// SHARED END
