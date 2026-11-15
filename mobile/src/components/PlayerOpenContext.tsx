import React, { createContext, useCallback, useContext, type ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';

import PressableScale from './PressableScale';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { stubPlayer } from '../lib/playerQuickView';
import type { PlayerRef } from '../lib/playerAnatomy';
import { canOpenPlayer, playerOpenLabel, PLAYER_TAP_MIN } from '../lib/playerTap';

/**
 * What a tap on any player does (twin of web ui/PlayerOpenContext.tsx). FantasyDesk needs no provider: the default opens
 * the real Player Quick View sheet. Fantasy Sim wraps its game screen in a provider that opens the sim sheet by the sim
 * player id, so every shared template (CompactPlayerCard, PlayerAccordionRow, TradeAssetCard, PlayerAvatarSlot) works in
 * both without a per-call wire-up.
 */
export const PlayerOpenContext = createContext<((player: PlayerRef) => void) | null>(null);

/** What a tap on a pick does (the sim's pick sheet). Null: a pick row stays plain. */
export interface PickTapRef {
  id: string;
  label: string;
  detail?: string | null;
}
export const PickOpenContext = createContext<((pick: PickTapRef) => void) | null>(null);

/** True inside a player tap target: a nested template renders plain (no Pressable inside a Pressable). */
export const TapScopeContext = createContext(false);

export function usePlayerOpener(): (player: PlayerRef) => void {
  const custom = useContext(PlayerOpenContext);
  const { openPlayer } = usePlayerQuickView();
  return useCallback(
    (player: PlayerRef) => {
      if (!canOpenPlayer(player)) return;
      if (custom) return custom(player);
      openPlayer(stubPlayer({ player_id: String(player.id), name: player.name, position: player.position ?? null, team: player.team ?? null }));
    },
    [custom, openPlayer],
  );
}

/**
 * THE player tap target: one accessible button (role button, 44pt minimum, the shared PressableScale press feedback)
 * around whatever identity markup a template draws. Plain markup when the player has no id, when the caller opted out
 * with `nonInteractive` (a reason string), or when it already sits inside a tap target.
 */
export function PlayerTap({
  player,
  onOpen,
  nonInteractive,
  style,
  minHeight = PLAYER_TAP_MIN,
  children,
}: {
  player: PlayerRef;
  onOpen?: () => void;
  nonInteractive?: string;
  style?: StyleProp<ViewStyle>;
  minHeight?: number;
  children: ReactNode;
}) {
  const open = usePlayerOpener();
  const inScope = useContext(TapScopeContext);
  if (inScope || nonInteractive || (!onOpen && !canOpenPlayer(player))) return <>{children}</>;
  return (
    <PressableScale accessibilityRole="button" accessibilityLabel={playerOpenLabel(player.name)} onPress={() => (onOpen ? onOpen() : open(player))} style={[{ minHeight }, style]}>
      <TapScopeContext.Provider value>{children}</TapScopeContext.Provider>
    </PressableScale>
  );
}

/** THE pick tap target (pick twin of PlayerTap). */
export function PickTap({ id, label, detail, onOpen, nonInteractive, children }: { id?: string; label: string; detail?: string | null; onOpen?: () => void; nonInteractive?: string; children: ReactNode }) {
  const open = useContext(PickOpenContext);
  const inScope = useContext(TapScopeContext);
  if (inScope || nonInteractive || (!onOpen && !(open && id))) return <>{children}</>;
  return (
    <PressableScale accessibilityRole="button" accessibilityLabel={`Open ${label}`} onPress={() => (onOpen ? onOpen() : open && id ? open({ id, label, detail }) : undefined)} style={{ minHeight: PLAYER_TAP_MIN }}>
      <TapScopeContext.Provider value>{children}</TapScopeContext.Provider>
    </PressableScale>
  );
}
