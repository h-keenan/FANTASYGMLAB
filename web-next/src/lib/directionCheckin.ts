/**
 * Dashboard direction check-in: a few times a season the Dashboard asks whether
 * the declared Team Situation (Rebuilding / Balanced / Competing) still fits.
 * The server decides WHEN (modules/direction_checkin.py: start of season, mid-
 * season, trade deadline, playoff push; rate-limited, one answer ends a moment
 * for the season) and writes the words; this file holds the response shapes and
 * the tiny state machine both platforms' cards share. It has no imports and no
 * platform code (web-next and mobile hold byte-identical copies,
 * scripts/check_lib_twins.mjs). Answering a change goes through the normal
 * Team Situation write; the check-in only records that the question was handled.
 */

export type DirectionCheckinAction = "kept" | "changed" | "dismissed";

export interface DirectionCheckinOption {
  value: string;
  label: string;
}

/** GET /v1/leagues/{id}/direction-checkin. `show: false` carries only `reason`. */
export interface DirectionCheckinResponse {
  ok: boolean;
  show: boolean;
  reason?: string;
  moment?: string;
  moment_key?: string;
  moment_label?: string;
  week?: number | null;
  stance?: string;
  stance_label?: string;
  options?: DirectionCheckinOption[];
  headline?: string;
  body?: string;
  keep_label?: string;
  dismiss_label?: string;
}

export interface DirectionCheckinPrompt {
  momentKey: string;
  stance: string;
  stanceLabel: string;
  headline: string;
  body: string;
  keepLabel: string;
  dismissLabel: string;
  options: DirectionCheckinOption[];
}

/** The prompt to render, or null unless the server said show and sent everything the card needs. */
export function directionCheckinPrompt(res: DirectionCheckinResponse | null | undefined): DirectionCheckinPrompt | null {
  if (!res || !res.ok || res.show !== true) return null;
  if (!res.moment_key || !res.headline || !res.body || !res.stance) return null;
  return {
    momentKey: res.moment_key,
    stance: res.stance,
    stanceLabel: res.stance_label || res.stance,
    headline: res.headline,
    body: res.body,
    keepLabel: res.keep_label || "Still fits",
    dismissLabel: res.dismiss_label || "Not now",
    options: (res.options ?? []).filter((o) => o && o.value && o.label),
  };
}

export function directionSwitchLabel(option: DirectionCheckinOption): string {
  return `Switch to ${option.label}`;
}

export function directionChangedMessage(label: string): string {
  return `Direction set to ${label}. Trade ideas and values will use it from here.`;
}

export type DirectionCheckinState =
  | { phase: "idle" } // nothing read yet
  | { phase: "hidden" } // read and nothing to ask, or answered: never reopens
  | { phase: "ready"; prompt: DirectionCheckinPrompt; error: string }
  | { phase: "saving"; prompt: DirectionCheckinPrompt }
  | { phase: "changed"; label: string };

export const DIRECTION_CHECKIN_INITIAL: DirectionCheckinState = { phase: "idle" };

export type DirectionCheckinEvent =
  | { type: "loaded"; response: DirectionCheckinResponse | null }
  | { type: "save" }
  /** The answer was handled. A "changed" answer carries the new direction's label. */
  | { type: "answered"; action: DirectionCheckinAction; label?: string }
  /** Setting the new direction failed: stay open so the player can retry. */
  | { type: "failed" };

/**
 * The first `loaded` shows the card only for a complete `show: true` answer;
 * any other answer (or a failed read) hides it, so a read problem never nags.
 * Nothing reopens a hidden card: not a second load, not a late response. Kept
 * and dismissed hide it for good; a change shows one confirmation line.
 * Recording problems are not surfaced (the server only uses the record to
 * avoid asking again), only a failed direction change is.
 */
export function directionCheckinReducer(state: DirectionCheckinState, event: DirectionCheckinEvent): DirectionCheckinState {
  switch (event.type) {
    case "loaded": {
      if (state.phase !== "idle") return state;
      const prompt = directionCheckinPrompt(event.response);
      return prompt ? { phase: "ready", prompt, error: "" } : { phase: "hidden" };
    }
    case "save":
      return state.phase === "ready" ? { phase: "saving", prompt: state.prompt } : state;
    case "answered":
      if (state.phase !== "saving" && state.phase !== "ready") return state;
      return event.action === "changed" && event.label ? { phase: "changed", label: event.label } : { phase: "hidden" };
    case "failed":
      return state.phase === "saving" ? { phase: "ready", prompt: state.prompt, error: "Could not save that. Try again." } : state;
    default:
      return state;
  }
}
