"use client";

import { createContext, useCallback, useContext, type CSSProperties, type MouseEvent, type ReactNode } from "react";

import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { canOpenPlayer, playerOpenLabel } from "@/lib/playerTap";
import type { PlayerRef } from "@/lib/playerAnatomy";

/**
 * What a tap on any player does. FantasyDesk needs no provider: the default opens the real Player Quick View. Fantasy
 * Sim wraps its game screen in a provider that opens the sim PQV by the sim player id, so every shared template
 * (CompactPlayerCard, PlayerAccordionRow, TradeAssetCard, PlayerAvatarSlot) works in both without a per-call wire-up.
 */
export const PlayerOpenContext = createContext<((player: PlayerRef) => void) | null>(null);

/** What a tap on a pick does (the sim's pick sheet). Null: a pick row stays plain text. */
export interface PickTapRef {
  id: string;
  label: string;
  /** "via Rivals · Projected near the top of the round." */
  detail?: string | null;
}
export const PickOpenContext = createContext<((pick: PickTapRef) => void) | null>(null);

/**
 * True inside a player tap target (a PlayerTap, the legacy PlayerIdentityTrigger): a nested template then renders plain,
 * so a row can never put a button inside a button.
 */
export const TapScopeContext = createContext(false);

/** The opener for a player ref, or null when that player cannot be opened (no id). */
export function usePlayerOpener(): ((player: PlayerRef) => void) | null {
  const custom = useContext(PlayerOpenContext);
  const { openPlayer } = usePlayerQuickView();
  return useCallback(
    (player: PlayerRef) => {
      if (!canOpenPlayer(player)) return;
      if (custom) return custom(player);
      openPlayer({ player_id: String(player.id), name: player.name, position: player.position ?? null, team: player.team ?? null, age: player.age ?? null });
    },
    [custom, openPlayer],
  );
}

/**
 * THE player tap target: wraps whatever identity markup a template draws in one real button (role button, 44px
 * minimum, the global press feedback of every button). Falls back to plain markup when the player has no id or the
 * caller opted out with `nonInteractive` (a reason string; a template inside another tap target).
 */
export function PlayerTap({
  player,
  onOpen,
  nonInteractive,
  className = "block w-full min-w-0 text-left",
  style,
  minHeight = "var(--touch-target-min)",
  children,
}: {
  player: PlayerRef;
  /** Overrides the default opener (rare: a caller that already holds a richer row than the ref). */
  onOpen?: () => void;
  /** Opt out, with the reason (enforced by the tap-coverage test). */
  nonInteractive?: string;
  className?: string;
  style?: CSSProperties;
  minHeight?: string | number;
  children: ReactNode;
}) {
  const open = usePlayerOpener();
  const inScope = useContext(TapScopeContext);
  if (inScope || nonInteractive || (!onOpen && !canOpenPlayer(player))) return <>{children}</>;
  return (
    <button
      type="button"
      aria-label={playerOpenLabel(player.name)}
      data-player-tap="true"
      className={className}
      style={{ background: "none", border: 0, padding: 0, minHeight, ...style }}
      onClick={(event: MouseEvent) => {
        event.stopPropagation();
        if (onOpen) onOpen();
        else open?.(player);
      }}
    >
      <TapScopeContext.Provider value>{children}</TapScopeContext.Provider>
    </button>
  );
}
