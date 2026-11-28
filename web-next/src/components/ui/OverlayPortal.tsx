"use client";

import { useEffect, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { lockScroll, unlockScroll } from "@/lib/scrollLock";

const subscribeNever = () => () => {};

/**
 * THE way a full-viewport layer (backdrop, scrim, dialog, click-catcher) is mounted: portaled to <body>.
 *
 * A `position: fixed` element is positioned against the nearest ancestor that has a transform, filter, backdrop-filter,
 * will-change, contain or perspective, NOT the viewport. App pages are full of those (`.glass-surface` has a
 * backdrop-filter, motion wrappers animate transform), so a pop-up rendered in the tree was boxed into the card that
 * opened it: anchored at the top of the page, clipped, scrolling away with it, no scrim. Rendering at <body> escapes every
 * such ancestor. Every shell in the app (ui/Sheet, PopupShell, StoryCarousel, TradePickerSheet, SimSheet) portals; a
 * hand-built overlay wraps its root in this. Guard: lib/overlayPortal.test.ts.
 *
 * `lockScroll` (for a modal layer that does not register with the overlay stack) also locks body scroll while mounted.
 *
 * Renders nothing on the server and during hydration (overlays are only ever opened on the client).
 */
export function OverlayPortal({ children, lockScroll: lock = false }: { children: ReactNode; lockScroll?: boolean }) {
  const mounted = useSyncExternalStore(subscribeNever, () => true, () => false);
  useEffect(() => {
    if (!lock) return;
    lockScroll();
    return () => unlockScroll();
  }, [lock]);
  return mounted ? createPortal(children, document.body) : null;
}
