"use client";

import { useCallback, useEffect, useId, useRef, useSyncExternalStore } from "react";

import { overlayStack, type OverlayKind } from "@/lib/overlayStack";

export type OverlayHandle = {
  id: string;
  /** A sheet that is open but hidden behind a newer one: keep it mounted, render it `hidden`. */
  hidden: boolean;
  /** Newest overlay: it owns focus and Escape. */
  isTop: boolean;
  /** Title of the sheet this one was opened from, for "‹ Back to ...". Null when it is the first. */
  backTitle: string | null;
  /** Close just this overlay (returns to the one below). */
  back: () => void;
  /** The X: close every overlay and return to the page. */
  closeAll: () => void;
  /** z-index for this overlay's layer (dialogs above sheets). */
  zIndex: number;
};

/**
 * Register a pop-up with THE overlay stack (lib/overlayStack.ts). Every pop-up shell calls this once: the stack decides
 * which one is visible, owns browser-back, scroll lock and layering (components/OverlayRuntime.tsx), and the shell only
 * renders `hidden` / the Back button / its own close. See docs/ui-patterns.md "Overlays".
 *
 * `onClose` must close THIS overlay (flip the owner's open state).
 */
export function useOverlay({ title, onClose, kind = "sheet", enabled = true }: { title: string; onClose: () => void; kind?: OverlayKind; enabled?: boolean }): OverlayHandle {
  const id = useId();
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);
  const dismiss = useCallback(() => closeRef.current(), []);

  useSyncExternalStore(overlayStack.subscribe, overlayStack.version, overlayStack.version);

  useEffect(() => {
    if (!enabled) return;
    overlayStack.open({ id, kind, title, dismiss });
    return () => overlayStack.close(id);
  }, [enabled, id, kind, title, dismiss]);

  return {
    id,
    hidden: enabled && overlayStack.isHidden(id),
    isTop: enabled && overlayStack.isTop(id),
    backTitle: enabled ? (overlayStack.previousSheet(id)?.title ?? null) : null,
    back: dismiss,
    closeAll: () => {
      overlayStack.closeAll();
    },
    zIndex: overlayStack.layer(id),
  };
}
