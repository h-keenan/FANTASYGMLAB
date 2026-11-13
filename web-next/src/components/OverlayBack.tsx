"use client";

import type { OverlayHandle } from "@/lib/useOverlay";

/** "‹ Back to Trade picker" at the top of a pop-up that was opened from another one. Renders nothing for the first. */
export function OverlayBack({ overlay }: { overlay: Pick<OverlayHandle, "backTitle" | "back"> }) {
  if (!overlay.backTitle) return null;
  return (
    <button type="button" className="overlay-back" onClick={overlay.back} data-testid="overlay-back">
      <span aria-hidden="true">‹</span> Back to {overlay.backTitle}
    </button>
  );
}
