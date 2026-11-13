// State machine and copy for `ConfirmInPlace` (web + mobile twins): a
// destructive control that, on first tap, morphs in place into a confirmation
// instead of acting, opening a dialog, or growing the page.
//
// Two modes:
//   "tap-again"  the control keeps its footprint and its label becomes
//                "Tap again to confirm"; a second tap acts; reverts on its own
//                after TAP_AGAIN_REVERT_MS. Use for quick, low-regret actions
//                (sign out, reset lineup).
//   "ask"        the control is replaced, same footprint, by
//                "<prompt> [Confirm] [Keep]". Use when the action loses data
//                (delete a game, remove a league).
//
// Idle -> armed -> busy -> (idle | error). Pure and synchronous so it can be
// unit-tested without timers; the component owns the timers and calls
// `reduceConfirm` with a "timeout" event.

export type ConfirmMode = "tap-again" | "ask";
export type ConfirmPhase = "idle" | "armed" | "busy" | "error";
export type ConfirmEvent = "arm" | "cancel" | "confirm" | "succeeded" | "failed" | "timeout";

/** "Tap again to confirm" reverts on its own after this long. */
export const TAP_AGAIN_REVERT_MS = 4000;
/** The "ask" prompt stays longer: it holds a sentence the person is reading. */
export const ASK_REVERT_MS = 8000;
/** How long an UndoToast stays up before the removal is final. */
export const UNDO_TOAST_MS = 6000;

export function reduceConfirm(phase: ConfirmPhase, event: ConfirmEvent): ConfirmPhase {
  switch (event) {
    case "arm":
      return phase === "idle" || phase === "error" ? "armed" : phase;
    case "confirm":
      // In "tap-again" mode the second tap on the same control is the confirm.
      return phase === "armed" || phase === "error" ? "busy" : phase;
    case "cancel":
    case "timeout":
      // Never cancel mid-request: the action is already on its way.
      return phase === "busy" ? phase : "idle";
    case "succeeded":
      return phase === "busy" ? "idle" : phase;
    case "failed":
      return phase === "busy" ? "error" : phase;
  }
}

export function revertMs(mode: ConfirmMode): number {
  return mode === "tap-again" ? TAP_AGAIN_REVERT_MS : ASK_REVERT_MS;
}

export type ConfirmCopy = {
  /** Trigger label (button variants) or accessible name (icon / row). */
  label: string;
  /** Question shown in "ask" mode. */
  prompt?: string;
  /** Label of the destructive button in "ask" mode. */
  confirmLabel?: string;
  keepLabel?: string;
  errorText?: string;
};

export const DEFAULT_ERROR_TEXT = "That did not work. Try again.";

/** What a screen reader hears when the phase changes. Empty string = say nothing. */
export function confirmAnnouncement(phase: ConfirmPhase, mode: ConfirmMode, copy: ConfirmCopy): string {
  if (phase === "armed") {
    return mode === "tap-again"
      ? `Tap again to confirm: ${copy.label}.`
      : `${copy.prompt ?? "Are you sure?"} ${copy.confirmLabel ?? "Confirm"} or ${copy.keepLabel ?? "Keep"}.`;
  }
  if (phase === "busy") return "Working.";
  if (phase === "error") return copy.errorText ?? DEFAULT_ERROR_TEXT;
  return "";
}
