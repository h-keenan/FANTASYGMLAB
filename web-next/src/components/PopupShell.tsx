"use client";

import { useEffect, useRef, type CSSProperties, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { OverlayBack } from "@/components/OverlayBack";
import { trapTabKey } from "@/lib/focusTrap";
import { SheetHandle } from "@/components/SheetHandle";
import { useOverlay } from "@/lib/useOverlay";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";
import { SheetCloseButton } from "@/components/ui/SheetChrome";

/**
 * The shell for a hand-built pop-up (`.pqv-backdrop` + `.pqv-modal`): registers with THE overlay stack (one pop-up at a
 * time, Back row, browser back, scroll lock and layering are the overlay runtime's), swipe-down-to-dismiss, the grab
 * handle, the X, Escape = Back, focus in when visible. Children render inside the modal after the chrome.
 *
 * Use this for any new pop-up that does not fit `ui/Sheet`; see docs/ui-patterns.md "Overlays".
 */
export function PopupShell({
  title,
  onClose,
  labelledBy,
  ariaLabel,
  closeLabel,
  modalClassName = "",
  backdropClassName = "",
  modalStyle,
  portal = true,
  children,
}: {
  /** Names the pop-up for "‹ Back to <title>" on the one opened from it. */
  title: string;
  onClose: () => void;
  /** id of the visible heading inside `children`, or give `ariaLabel`. */
  labelledBy?: string;
  ariaLabel?: string;
  /** Accessible name of the X (default `Close <title>`). */
  closeLabel?: string;
  modalClassName?: string;
  backdropClassName?: string;
  modalStyle?: CSSProperties;
  portal?: boolean;
  children: ReactNode;
}) {
  const { sheetRef, sheetStyle, backdropStyle } = useSheetDragDismiss<HTMLDivElement>({ onDismiss: onClose });
  const overlay = useOverlay({ title, onClose });
  const visible = !overlay.hidden;
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (visible) closeRef.current?.focus({ preventScroll: true });
  }, [visible]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    event.stopPropagation();
    if (event.key === "Escape") overlay.back();
    else trapTabKey(event, sheetRef.current);
  };

  const shell = (
    <div
      className={`pqv-backdrop ${backdropClassName}`.trim()}
      style={backdropStyle}
      hidden={overlay.hidden}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) overlay.closeAll();
      }}
      onKeyDown={onKeyDown}
    >
      <div
        ref={sheetRef}
        className={`pqv-modal ${modalClassName}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={labelledBy ? undefined : (ariaLabel ?? title)}
        style={{ ...sheetStyle, ...modalStyle }}
      >
        <SheetHandle />
        <OverlayBack overlay={overlay} />
        <SheetCloseButton ref={closeRef} label={closeLabel ?? `Close ${title}`} onClose={overlay.closeAll} />
        {children}
      </div>
    </div>
  );
  return portal && typeof document !== "undefined" ? createPortal(shell, document.body) : shell;
}
