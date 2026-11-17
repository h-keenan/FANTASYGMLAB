"use client";

import { forwardRef, type ReactNode, type Ref } from "react";

import "./ui.css";

/**
 * THE sheet / popup chrome (header rewrite phase 4; docs/audits/2026-11-header-rewrite.md, "Sheet" template). One close button and one
 * title block, so `Sheet`, `PopupShell` (PQV-style popups), the trade picker and the Sim claim dialog no longer each draw their own.
 * Slots: back (OverlayBack, rendered by the shell above this), title, subtitle, actions, close. Twin: mobile/src/components/SheetChrome.tsx.
 *
 * - `placement="corner"`: the round glass X floating top right of a hero-style sheet (PQV, team and player popups).
 * - `placement="inline"`: the same X as the last item of a header row (`SheetHeader`).
 */
export const SheetCloseButton = forwardRef<HTMLButtonElement, { label: string; onClose: () => void; placement?: "corner" | "inline" }>(
  function SheetCloseButton({ label, onClose, placement = "corner" }, ref) {
    return (
      <button
        ref={ref}
        type="button"
        className={`pqv-close${placement === "inline" ? " sheet-close-inline" : ""}`}
        aria-label={label}
        data-sheet-close=""
        onClick={onClose}
      >
        <span aria-hidden="true">×</span>
      </button>
    );
  },
);

export type SheetHeaderProps = {
  /** id of the title element (the dialog's aria-labelledby). */
  titleId: string;
  title: string;
  /** One line under the title. */
  subtitle?: string | null;
  /** Small uppercase accent line above the title (the nav sheet's "FANTASYDESK"). */
  eyebrow?: string;
  subtitleId?: string;
  /** Keep the title for assistive tech but hide it visually. */
  hideTitle?: boolean;
  /** Content before the title (a tone dot, an avatar). */
  leading?: ReactNode;
  /** Controls between the title and the close button. */
  actions?: ReactNode;
  onClose: () => void;
  closeLabel?: string;
  closeRef?: Ref<HTMLButtonElement>;
};

/** Title, subtitle, actions and the close button on one row. */
export function SheetHeader({ titleId, title, subtitle, eyebrow, subtitleId, hideTitle = false, leading, actions, onClose, closeLabel, closeRef }: SheetHeaderProps) {
  return (
    <header className="ui-sheet-header" data-sheet-header="">
      {leading}
      <div className="min-w-0 flex-1">
        {eyebrow && !hideTitle ? <p className="ui-sheet-eyebrow">{eyebrow}</p> : null}
        <h2 id={titleId} className={hideTitle ? "sr-only" : "ui-sheet-title"}>
          {title}
        </h2>
        {subtitle ? (
          <p id={subtitleId} className="ui-sheet-desc">
            {subtitle}
          </p>
        ) : null}
      </div>
      {actions}
      <SheetCloseButton ref={closeRef} label={closeLabel ?? `Close ${title}`} onClose={onClose} placement="inline" />
    </header>
  );
}
