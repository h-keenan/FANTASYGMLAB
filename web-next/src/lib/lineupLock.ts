/**
 * The one client rule for "is this starter a lineup problem?" (twin of modules/lineup_lock.py, byte-identical with
 * mobile/src/lib/lineupLock.ts). A player is locked the moment his own NFL game kicks off (in progress or final): he can
 * no longer be benched or started, so he is never a hole, never a swap target and never behind a "Fix lineup" button.
 * A locked starter who is hurt is information only ("Left game (injury)"). Unknown kickoff data is "not locked".
 * The server sends the verdicts (`lineup_issue`, `left_game`); the fallbacks derive the same answer from the raw fields
 * so an older API build behaves the same.
 */
export interface LockAwareStarter {
  ruled_out?: boolean | null;
  on_bye?: boolean | null;
  start_ineligible_reason?: string | null;
  injury_label?: string | null;
  game_started?: boolean | null;
  game_locked?: boolean | null;
  lineup_issue?: boolean | null;
  left_game?: boolean | null;
}

/** Reasons a starter cannot play for a fixable reason; "Game started" is a lock, not a problem. */
const FIXABLE_REASONS = new Set(["Bye", "Out", "IR", "PUP", "Suspended"]);

export const LEFT_GAME_LABEL = "Left game (injury)";

export function isLineupLocked(p: LockAwareStarter): boolean {
  if (p.on_bye || p.start_ineligible_reason === "Bye") return false;
  return p.game_started === true || p.game_locked === true;
}

/** An Out / bye / IR starter whose game has NOT started: the only kind a manager can still fix. */
export function isActionableLineupIssue(p: LockAwareStarter): boolean {
  if (typeof p.lineup_issue === "boolean") return p.lineup_issue;
  if (isLineupLocked(p)) return false;
  return Boolean(p.ruled_out || p.on_bye || (p.start_ineligible_reason && FIXABLE_REASONS.has(p.start_ineligible_reason)));
}

/** A locked starter who is hurt: shown as information, never as advice. */
export function leftGame(p: LockAwareStarter): boolean {
  if (typeof p.left_game === "boolean") return p.left_game;
  return isLineupLocked(p) && Boolean(p.ruled_out || (p.injury_label && p.injury_label.trim()));
}
