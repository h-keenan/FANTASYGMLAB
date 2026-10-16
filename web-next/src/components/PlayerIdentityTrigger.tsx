"use client";

import type { ReactNode } from "react";

import { usePlayerQuickView, type PlayerQuickViewIdentity } from "@/context/PlayerQuickViewContext";

/**
 * One consistent tap-trigger for every player identity row in the app —
 * wraps whatever markup a page already renders (PositionBadge + name +
 * OvrGauge, a trade asset row, a draft pick-recommendation card, ...) in a
 * plain, unstyled `<button>` that opens the shared PlayerQuickView modal
 * for that player. Pages don't need to hand-roll onClick/usePlayerQuickView
 * wiring themselves — just wrap the identity markup once, passing whatever
 * fields the row already has (most page row types already carry the exact
 * field names PlayerQuickViewIdentity expects, see its own docstring).
 *
 * Deliberately resets all button chrome (no border/background/padding) so
 * it's visually identical to the div/span it replaces — this is a tap
 * target, not a new button-styled element.
 */
export function PlayerIdentityTrigger({
  identity,
  className = "",
  children,
}: {
  identity: PlayerQuickViewIdentity;
  className?: string;
  children: ReactNode;
}) {
  const { openPlayer } = usePlayerQuickView();
  return (
    <button
      type="button"
      onClick={(event) => {
        // Several rows this wraps (e.g. TradeFinderContent's RosterPickRow)
        // are themselves inside a larger clickable row with its own
        // selection/toggle behavior — stop that outer handler from also
        // firing just because the player's name/badge was tapped.
        event.stopPropagation();
        openPlayer(identity);
      }}
      className={`appearance-none bg-transparent border-0 p-0 m-0 text-left cursor-pointer min-w-0 ${className}`.trim()}
    >
      {children}
    </button>
  );
}
