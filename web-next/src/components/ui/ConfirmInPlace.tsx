"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useReducer, useRef, type CSSProperties, type ReactNode } from "react";

import { Button, type ButtonVariant } from "@/components/Button";
import {
  DEFAULT_ERROR_TEXT,
  confirmAnnouncement,
  reduceConfirm,
  revertMs,
  type ConfirmMode,
} from "@/lib/confirmInPlace";

import "./ui.css";

export type ConfirmInPlaceProps = {
  /** "button" = text button, "icon" = icon-only (trash), "row" = a full-width row action. */
  variant?: "button" | "icon" | "row";
  /** Trigger text (button / row) or accessible name (icon). */
  label: string;
  /** Accessible name for the idle trigger when the visible text is shorter ("Remove" vs "Remove Team 3"). */
  ariaLabel?: string;
  /**
   * "tap-again": the control keeps its footprint, its label becomes "Tap again to confirm", reverts after 4 s.
   * "ask": the control is covered, in place, by "<prompt> [Confirm] [Keep]". Default: tap-again for
   * "button", ask for "icon" and "row".
   */
  mode?: ConfirmMode;
  /** Question for "ask" mode. */
  prompt?: string;
  /** Destructive button text in "ask" mode. Default: label. */
  confirmLabel?: string;
  keepLabel?: string;
  /** Runs on the confirming tap. Throw, reject or return false to show the error state. */
  onConfirm: () => void | boolean | Promise<void | boolean>;
  /** Shown in the error state. */
  errorText?: string;
  disabled?: boolean;
  /** Button look for the idle trigger. Destructive by default. */
  buttonVariant?: ButtonVariant;
  size?: "sm" | "md";
  /** Custom glyph for the icon variant (default: trash). */
  icon?: ReactNode;
  /**
   * Where "ask" mode paints its panel. "self" covers just this control, growing to the left;
   * "parent" covers the whole nearest positioned ancestor (give the row `position: relative`),
   * which is what a list row wants. Either way the layout never moves.
   */
  overlay?: "self" | "parent";
  className?: string;
  testId?: string;
  /**
   * Render the trigger as a plain text button (no Button chrome) styled by `triggerClassName` /
   * `triggerStyle`, for places that already have their own look, like a menu item. The armed
   * state still swaps the label in place.
   */
  plain?: boolean;
  triggerClassName?: string;
  triggerStyle?: CSSProperties;
  triggerRole?: string;
};

function TrashGlyph() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2.5 4h11M6 4V2.5h4V4M4 4l.6 9h6.8L12 4M6.6 6.5v4M9.4 6.5v4" />
    </svg>
  );
}

/**
 * A destructive control that confirms where it stands. First tap morphs it in
 * place (same footprint, nothing below it moves); the second tap acts.
 * See lib/confirmInPlace.ts for the state machine and docs/ui-patterns.md.
 *
 * a11y: the trigger carries aria-expanded while armed; a polite live region
 * announces the question, "Working", and errors; focus lands on the SAFE
 * choice (Keep) in "ask" mode and returns to the trigger on cancel; Escape
 * and a press outside cancel; the destructive button is never the first
 * focus target.
 */
export function ConfirmInPlace({
  variant = "button",
  label,
  ariaLabel,
  mode,
  prompt = "Are you sure?",
  confirmLabel,
  keepLabel = "Keep",
  onConfirm,
  errorText = DEFAULT_ERROR_TEXT,
  disabled = false,
  buttonVariant,
  size = "md",
  icon,
  overlay = "self",
  className = "",
  testId,
  plain = false,
  triggerClassName = "",
  triggerStyle: plainStyle,
  triggerRole,
}: ConfirmInPlaceProps) {
  // An icon has no room for a sentence or a long label, so it always asks.
  const resolvedMode: ConfirmMode = variant === "icon" ? "ask" : (mode ?? (variant === "button" ? "tap-again" : "ask"));
  const [phase, dispatch] = useReducer(reduceConfirm, "idle");
  const rootRef = useRef<HTMLSpanElement>(null);
  const panelRef = useRef<HTMLSpanElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const wasArmed = useRef(false);
  const panelId = useId();
  const confirmText = confirmLabel ?? label;
  // Derived, not stored: the live region announces whenever this text changes.
  const announcement = confirmAnnouncement(phase, resolvedMode, { label, prompt, confirmLabel: confirmText, keepLabel, errorText });

  // Auto-revert while armed (never while a request is running or showing an error).
  useEffect(() => {
    if (phase !== "armed") return;
    const timer = window.setTimeout(() => dispatch("timeout"), revertMs(resolvedMode));
    return () => window.clearTimeout(timer);
  }, [phase, resolvedMode]);

  // Focus the safe choice when "ask" opens; hand focus back to the trigger when it closes.
  const open = phase !== "idle";
  useEffect(() => {
    if (resolvedMode === "ask" && open && !wasArmed.current) keepRef.current?.focus({ preventScroll: true });
    if (!open && wasArmed.current) rootRef.current?.querySelector<HTMLElement>("[data-confirm-trigger]")?.focus({ preventScroll: true });
    wasArmed.current = open;
  }, [open, resolvedMode]);

  // "self" panels grow towards whichever side has room, so a control near a screen edge never pushes
  // its question off-screen. ("parent" panels fill the row and need no measuring.)
  useLayoutEffect(() => {
    const panel = panelRef.current;
    const root = rootRef.current;
    if (!panel || !root || overlay !== "self") return;
    const { left, right } = root.getBoundingClientRect();
    const width = panel.offsetWidth;
    const room = window.innerWidth - 8;
    if (left + width <= room) {
      panel.style.left = "0";
      panel.style.right = "auto";
    } else {
      panel.style.right = "0";
      panel.style.left = "auto";
      if (right - width < 8) panel.style.transform = `translateX(${8 - (right - width)}px)`;
    }
  });

  // A press or focus outside cancels.
  useEffect(() => {
    if (phase !== "armed" && phase !== "error") return;
    const onPointer = (event: Event) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) dispatch("cancel");
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [phase]);

  const run = useCallback(async () => {
    dispatch("confirm");
    try {
      const result = await onConfirm();
      dispatch(result === false ? "failed" : "succeeded");
    } catch {
      dispatch("failed");
    }
  }, [onConfirm]);

  function onTrigger() {
    if (phase === "idle") dispatch("arm");
    else if (resolvedMode === "tap-again" && phase === "armed") void run();
  }

  const destructive = buttonVariant ?? (variant === "button" ? "dangerOutline" : "dangerOutline");
  const armedTapAgain = resolvedMode === "tap-again" && phase === "armed";
  const showPanel = (resolvedMode === "ask" && phase !== "idle") || phase === "error";
  const busy = phase === "busy";

  // The trigger. In tap-again mode both labels share one grid cell so the width is the wider of the two.
  const triggerStyle: CSSProperties = {
    borderColor: "var(--color-danger)",
    color: "var(--color-danger)",
    background: armedTapAgain ? "color-mix(in srgb, var(--color-danger) 16%, transparent)" : "transparent",
  };

  let trigger: ReactNode;
  if (variant === "icon") {
    trigger = (
      <button
        type="button"
        data-confirm-trigger=""
        className="ui-confirm-icon"
        style={triggerStyle}
        aria-label={label}
        aria-expanded={showPanel || undefined}
        aria-controls={showPanel ? panelId : undefined}
        disabled={disabled || busy}
        onClick={onTrigger}
      >
        {icon ?? <TrashGlyph />}
      </button>
    );
  } else if (resolvedMode === "tap-again") {
    const labels = (
      <span className="ui-confirm-sizer">
        <span style={{ gridArea: "1 / 1", visibility: armedTapAgain ? "hidden" : "visible" }} aria-hidden={armedTapAgain}>
          {label}
        </span>
        <span style={{ gridArea: "1 / 1", visibility: armedTapAgain ? "visible" : "hidden" }} aria-hidden={!armedTapAgain}>
          Tap again to confirm
        </span>
      </span>
    );
    const timer = phase === "armed" ? <span className="ui-confirm-timer" aria-hidden="true" style={{ animationDuration: `${revertMs("tap-again")}ms` }} /> : null;
    trigger = plain ? (
      <button
        type="button"
        role={triggerRole}
        data-confirm-trigger=""
        aria-label={armedTapAgain ? undefined : ariaLabel}
        aria-expanded={phase === "armed" || undefined}
        disabled={disabled || busy}
        onClick={onTrigger}
        className={`ui-confirm-trigger ${triggerClassName}`.trim()}
        style={plainStyle}
      >
        {labels}
        {timer}
      </button>
    ) : (
      <Button
        variant={destructive}
        size={size}
        fullWidth={variant === "row"}
        disabled={disabled}
        loading={busy}
        aria-label={armedTapAgain ? undefined : ariaLabel}
        aria-expanded={phase === "armed" || undefined}
        onClick={onTrigger}
        className={`ui-confirm-trigger ${armedTapAgain ? "ui-confirm-armed" : ""}`}
        style={armedTapAgain ? triggerStyle : undefined}
        data-confirm-trigger=""
      >
        {labels}
        {timer}
      </Button>
    );
  } else {
    trigger = plain ? (
      <button
        type="button"
        role={triggerRole}
        data-confirm-trigger=""
        aria-label={ariaLabel}
        aria-expanded={showPanel || undefined}
        aria-controls={showPanel ? panelId : undefined}
        disabled={disabled}
        onClick={onTrigger}
        className={`ui-confirm-trigger ${triggerClassName}`.trim()}
        style={plainStyle}
      >
        {label}
      </button>
    ) : (
      <Button
        variant={destructive}
        size={size}
        fullWidth={variant === "row"}
        disabled={disabled}
        aria-label={ariaLabel}
        aria-expanded={showPanel || undefined}
        aria-controls={showPanel ? panelId : undefined}
        onClick={onTrigger}
        data-confirm-trigger=""
        className="ui-confirm-trigger"
      >
        {label}
      </Button>
    );
  }

  return (
    <span
      ref={rootRef}
      className={`ui-confirm ${overlay === "parent" ? "ui-confirm-parent" : ""} ${className}`.trim()}
      data-phase={phase}
      data-testid={testId}
      onKeyDown={(event) => {
        if (event.key === "Escape" && phase !== "idle" && phase !== "busy") {
          event.stopPropagation();
          dispatch("cancel");
        }
      }}
    >
      {/* Keeps the footprint while the panel covers it. */}
      <span style={{ visibility: showPanel ? "hidden" : "visible", display: "contents" }} aria-hidden={showPanel || undefined}>
        {trigger}
      </span>
      {showPanel ? (
        <span ref={panelRef} id={panelId} role="group" aria-label={prompt} className="ui-confirm-panel" data-state={phase}>
          <span className="ui-confirm-text">{phase === "error" ? errorText : prompt}</span>
          <span className="ui-confirm-actions">
            <Button variant="danger" size="sm" loading={busy} onClick={() => void run()}>
              {phase === "error" ? "Retry" : confirmText}
            </Button>
            <button ref={keepRef} type="button" className="ui-confirm-keep" disabled={busy} onClick={() => dispatch("cancel")}>
              {phase === "error" ? "Cancel" : keepLabel}
            </button>
          </span>
        </span>
      ) : null}
      <span className="sr-only" role="status" aria-live={phase === "error" ? "assertive" : "polite"}>
        {announcement}
      </span>
    </span>
  );
}
