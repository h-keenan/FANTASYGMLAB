"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import { PlayerQuickView } from "@/components/PlayerQuickView";

/**
 * Minimal player-identity summary a caller already has in hand (every page
 * that renders OvrGauge/PositionBadge already holds a row shaped like this
 * — RankedPlayer and its page-local siblings all share these field names).
 * GET .../quick-view is league-independent and doesn't return name/team/
 * photo (the client already has that from whatever list fetched this
 * player — see lib/api.ts's QuickViewResponse docstring), so the trigger
 * must pass it in rather than the modal re-deriving it.
 */
export interface PlayerQuickViewIdentity {
  player_id: string;
  name?: string | null;
  position?: string | null;
  team?: string | null;
  age?: number | null;
  status?: string | null;
  injury_status?: string | null;
  tier?: string | null;
  score?: number | null;
  overall_rank?: number | null;
  position_rank?: number | null;
  rank_unavailable_reason?: string | null;
  opportunity_label?: string | null;
  overall_rating?: number | null;
  /** Where this open came from (e.g. "My Team", "Trade Hub") — shown as a
   * small source label, same provenance app.py's open_player_quick_view
   * threads through via source_label. Purely cosmetic. */
  sourceLabel?: string;
  /** League context, so the modal's optional "Compare" quick action can
   * deep-link to /player-compare/{leagueId} pre-selecting this player
   * (matches the ?a=<playerId> convention PlayerRow's own "Compare" link
   * already uses). Omit on pages with no active league (e.g. College
   * Scouting) to hide that action. */
  leagueId?: string;
  leagueName?: string;
}

interface PlayerQuickViewContextValue {
  openPlayer: (identity: PlayerQuickViewIdentity) => void;
  closePlayer: () => void;
}

const PlayerQuickViewContext = createContext<PlayerQuickViewContextValue | undefined>(undefined);

export function PlayerQuickViewProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<PlayerQuickViewIdentity | null>(null);

  const openPlayer = useCallback((next: PlayerQuickViewIdentity) => {
    if (!next?.player_id) return;
    setIdentity(next);
  }, []);
  const closePlayer = useCallback(() => setIdentity(null), []);

  const value = useMemo<PlayerQuickViewContextValue>(() => ({ openPlayer, closePlayer }), [openPlayer, closePlayer]);

  return (
    <PlayerQuickViewContext.Provider value={value}>
      {children}
      {identity ? (
        // key={identity.player_id} forces a fresh mount per player (not just
        // a re-render), so PlayerQuickView's fetch effect starts from a
        // clean initial loading/detail/awards state instead of needing to
        // reset that state imperatively on every identity change.
        <PlayerQuickView key={identity.player_id} identity={identity} onClose={closePlayer} />
      ) : null}
    </PlayerQuickViewContext.Provider>
  );
}

const NOOP_VALUE: PlayerQuickViewContextValue = {
  openPlayer: () => {},
  closePlayer: () => {},
};

/** `openPlayer(identity)` opens the shared quick-view modal for any player
 * row on any page — the one tap-trigger every "player identity" row in the
 * app should call instead of hand-rolling its own popup. See
 * PlayerQuickViewIdentity above for the shape to pass.
 *
 * `RootLayout` always wraps the real app in `PlayerQuickViewProvider`, so
 * every page gets a working modal. Outside that tree (a component test
 * that renders e.g. `<MyTeamContent .../>` directly, with no app shell)
 * this degrades to a harmless no-op rather than throwing, so existing
 * per-page tests don't need to know this modal exists just to keep
 * rendering their own unrelated assertions. */
export function usePlayerQuickView(): PlayerQuickViewContextValue {
  const ctx = useContext(PlayerQuickViewContext);
  return ctx ?? NOOP_VALUE;
}
