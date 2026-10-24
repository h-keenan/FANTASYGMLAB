/**
 * First-run "Start here" checklist (new-user intake audit, 2026-10).
 * Pure logic, kept identical with mobile/src/lib/startHere.ts (a test on each
 * side pins the step list and copy). Storage differs per platform
 * (localStorage on web, AsyncStorage on mobile) and holds only per-device
 * convenience state, never anything the server needs.
 */

export type StartHereRoute = "matchup" | "trade_hub" | "waivers";

export interface StartHereStep {
  key: StartHereRoute;
  label: string;
  why: string;
}

export const START_HERE_TITLE = "Start here";
export const START_HERE_SUBTITLE = "Three quick looks to see what FantasyDesk does for your team.";
export const START_HERE_STEPS: readonly StartHereStep[] = [
  { key: "matchup", label: "Check your lineup", why: "Win odds and any swap worth making this week." },
  { key: "trade_hub", label: "See your best trade idea", why: "Or a clear hold when trading is not the move." },
  { key: "waivers", label: "Review waiver targets", why: "Ranked for your roster needs, not just the best available." },
];

/** Only accounts this young see the card, so existing users never get it. */
export const START_HERE_WINDOW_DAYS = 14;

export interface StartHereState {
  dismissed: boolean;
  done: StartHereRoute[];
}

export const EMPTY_START_HERE_STATE: StartHereState = { dismissed: false, done: [] };

export function startHereStorageKey(userId: string): string {
  return `fd:start-here:v1:${userId}`;
}

export function parseStartHereState(raw: string | null | undefined): StartHereState {
  if (!raw) return EMPTY_START_HERE_STATE;
  try {
    const parsed = JSON.parse(raw) as Partial<StartHereState> | null;
    const valid = new Set<string>(START_HERE_STEPS.map((step) => step.key));
    const done = Array.isArray(parsed?.done) ? parsed.done.filter((key): key is StartHereRoute => valid.has(key)) : [];
    return { dismissed: parsed?.dismissed === true, done: Array.from(new Set(done)) };
  } catch {
    return EMPTY_START_HERE_STATE;
  }
}

export function markStartHereStepDone(state: StartHereState, key: StartHereRoute): StartHereState {
  return state.done.includes(key) ? state : { ...state, done: [...state.done, key] };
}

export function startHereAllDone(state: StartHereState): boolean {
  return START_HERE_STEPS.every((step) => state.done.includes(step.key));
}

/** Show for a recently created account until it is dismissed or finished. */
export function shouldShowStartHere(
  state: StartHereState,
  accountCreatedAt: string | null | undefined,
  now: number = Date.now(),
): boolean {
  if (state.dismissed || startHereAllDone(state)) return false;
  const created = accountCreatedAt ? Date.parse(accountCreatedAt) : NaN;
  if (!Number.isFinite(created)) return false;
  return now - created <= START_HERE_WINDOW_DAYS * 24 * 60 * 60 * 1000;
}
