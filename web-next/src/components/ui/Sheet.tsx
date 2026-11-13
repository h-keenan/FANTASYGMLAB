"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useSyncExternalStore,
  type KeyboardEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";

import { SheetHandle } from "@/components/SheetHandle";
import { OverlayBack } from "@/components/OverlayBack";
import { useOverlay } from "@/lib/useOverlay";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";

import "./ui.css";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const subscribeNever = () => () => {};

export type SheetProps = {
  open: boolean;
  onClose: () => void;
  /** The dialog's accessible name and visible heading. */
  title: string;
  /** One line under the title. */
  description?: string;
  children: ReactNode;
  /** Sticky footer (an Apply bar, for example). Sits above the safe area. */
  footer?: ReactNode;
  /** "sm" is a compact popover-sized card on desktop; "md" (default) a 560px dialog; "lg" 720px. */
  size?: "sm" | "md" | "lg";
  /** Hide the visible heading (the title still names the dialog). */
  hideTitle?: boolean;
  /** Element to focus on open instead of the dialog's close button. */
  initialFocusRef?: RefObject<HTMLElement | null>;
  /** Extra class on the dialog surface. */
  className?: string;
  testId?: string;
};

/**
 * The one sheet. A bottom sheet on a phone, a centered dialog from 768px up.
 * Portaled to <body>, `role="dialog" aria-modal`, focus trapped and returned to
 * the trigger, Escape and backdrop close, body scroll locked, safe-area aware,
 * swipe-down to dismiss on touch.
 *
 * Overlay rule: one pop-up at a time. Opening a second sheet REPLACES the first
 * on screen (it stays mounted but hidden, so its scroll and draft state survive),
 * the newer one gets "‹ Back to <first>", browser/phone back returns to the first,
 * and the X closes everything. See lib/overlayStack.ts and docs/ui-patterns.md.
 *
 * Mount it with `open` toggled; its children are not rendered while closed.
 */
export function Sheet({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
  hideTitle = false,
  initialFocusRef,
  className = "",
  testId,
}: SheetProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descId = `${id}-desc`;
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  // False on the server and on hydration, true on the client: keeps the portal out of SSR without an effect.
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);
  const { sheetRef, sheetStyle, backdropStyle } = useSheetDragDismiss<HTMLDivElement>({ onDismiss: onClose, enabled: open });

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // THE overlay stack decides visibility, back-stack, history, scroll lock and layering (lib/overlayStack.ts).
  const overlay = useOverlay({ title, onClose, enabled: open });
  const hidden = overlay.hidden;

  // Remember what to focus on close.
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    return () => previousFocus?.focus?.({ preventScroll: true });
  }, [open]);

  // Move focus in when the sheet becomes the visible one (first open, or restored after a newer sheet closed).
  useEffect(() => {
    if (!open || hidden || !mounted) return;
    const target = initialFocusRef?.current ?? closeRef.current ?? sheetRef.current;
    target?.focus({ preventScroll: true });
  }, [open, hidden, mounted, initialFocusRef, sheetRef]);

  const onKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      // The sheet is a modal boundary: key events never reach a dialog underneath it
      // (React bubbles through portals, and a parent dialog's focus trap would steal focus).
      event.stopPropagation();
      if (event.key !== "Tab") return;
      const root = sheetRef.current;
      if (!root) return;
      const focusable = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
        (el) => !el.closest('[aria-hidden="true"], [hidden]'),
      );
      if (focusable.length === 0) {
        event.preventDefault();
        root.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || active === root || !root.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !root.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    },
    [sheetRef],
  );

  if (!open || !mounted) return null;

  return createPortal(
    <div
      className="ui-sheet-backdrop"
      data-hidden={hidden || undefined}
      hidden={hidden}
      style={{ ...backdropStyle, zIndex: overlay.zIndex }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) overlay.closeAll();
      }}
    >
      <div
        ref={sheetRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        className={`ui-sheet ui-sheet-${size} ${className}`.trim()}
        style={sheetStyle}
        onKeyDown={onKeyDown}
        data-testid={testId}
      >
        <SheetHandle />
        <OverlayBack overlay={overlay} />
        <header className="ui-sheet-header">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className={hideTitle ? "sr-only" : "ui-sheet-title"}>
              {title}
            </h2>
            {description ? (
              <p id={descId} className="ui-sheet-desc">
                {description}
              </p>
            ) : null}
          </div>
          <button ref={closeRef} type="button" className="ui-sheet-close" aria-label={`Close ${title}`} onClick={overlay.closeAll}>
            <span aria-hidden="true">×</span>
          </button>
        </header>
        <div className="ui-sheet-body">{children}</div>
        {footer ? <div className="ui-sheet-footer">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}
