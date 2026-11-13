import { useEffect, useId, useRef, useSyncExternalStore } from 'react';

import { overlayStack, type OverlayKind } from './overlayStack';

/**
 * Register a pop-up with THE overlay stack (lib/overlayStack.ts, same rules as web-next's lib/useOverlay.ts): one
 * pop-up on screen at a time, a newer one replaces the older on screen (the older stays mounted but hidden), Android
 * back / the Back row returns to it, the X closes everything.
 *
 * `SheetModal` calls this for every Modal-based pop-up, so the 30-odd existing sheets get the rule without changes;
 * `Sheet` calls it itself (it also needs `backTitle`). `onClose` must close THIS pop-up.
 */
export function useOverlay({ title, onClose, kind = 'sheet', enabled = true }: { title: string; onClose: () => void; kind?: OverlayKind; enabled?: boolean }) {
  const id = useId();
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useSyncExternalStore(overlayStack.subscribe, overlayStack.version, overlayStack.version);

  useEffect(() => {
    if (!enabled) return;
    overlayStack.open({ id, kind, title, dismiss: () => closeRef.current() });
    return () => overlayStack.close(id);
  }, [enabled, id, kind, title]);

  return {
    id,
    hidden: enabled && overlayStack.isHidden(id),
    isTop: enabled && overlayStack.isTop(id),
    backTitle: enabled ? (overlayStack.previousSheet(id)?.title ?? null) : null,
    back: () => closeRef.current(),
    closeAll: () => {
      overlayStack.closeAll();
    },
  };
}
