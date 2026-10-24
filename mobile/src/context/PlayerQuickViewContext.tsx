import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

import PlayerQuickViewSheet from '../components/PlayerQuickViewSheet';
import type { RankedPlayer } from '../lib/api';
import { buildQuickViewRequest, type QuickViewRequest } from '../lib/playerQuickView';

export interface OpenPlayerOptions {
  /** Omit on league-less surfaces (News): the sheet then shows only
   * league-independent data. */
  leagueId?: string | null;
  leagueName?: string | null;
  /** Small provenance label shown in the sheet, e.g. "Waivers". */
  sourceLabel?: string;
}

interface PlayerQuickViewContextValue {
  openPlayer: (player: RankedPlayer, options?: OpenPlayerOptions) => void;
  closePlayer: () => void;
}

const NOOP: PlayerQuickViewContextValue = { openPlayer: () => {}, closePlayer: () => {} };

const PlayerQuickViewContext = createContext<PlayerQuickViewContextValue>(NOOP);

/** Mounted once in RootNavigator. Every player tap in the app goes through
 * `usePlayerQuickView().openPlayer`, which opens the one shared sheet; the
 * sheet's "Full profile" action is the only path into PlayerDetail. */
export function PlayerQuickViewProvider({ children }: { children: React.ReactNode }) {
  const [request, setRequest] = useState<QuickViewRequest | null>(null);

  const openPlayer = useCallback((player: RankedPlayer, options?: OpenPlayerOptions) => {
    const next = buildQuickViewRequest(player, options, options?.sourceLabel);
    if (next) setRequest(next);
  }, []);
  const closePlayer = useCallback(() => setRequest(null), []);
  const value = useMemo(() => ({ openPlayer, closePlayer }), [openPlayer, closePlayer]);

  return (
    <PlayerQuickViewContext.Provider value={value}>
      {children}
      {request ? <PlayerQuickViewSheet key={request.player.player_id} request={request} onClose={closePlayer} /> : null}
    </PlayerQuickViewContext.Provider>
  );
}

export function usePlayerQuickView(): PlayerQuickViewContextValue {
  return useContext(PlayerQuickViewContext);
}
