import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

import type { ValuationLens } from '../lib/api';

export const DEFAULT_LENS: ValuationLens = 'Dynasty';

interface ValuationLensContextValue {
  getLens: (leagueId: string) => ValuationLens;
  setLens: (leagueId: string, lens: ValuationLens) => void;
}

const ValuationLensContext = createContext<ValuationLensContextValue | undefined>(undefined);

/**
 * One shared, per-league evaluation lens (Dynasty / Rebuild / Redraft) —
 * same "one control, every screen sees the same value" shape as
 * GmStanceContext, and for the same reason: this used to be independent
 * local useState in whichever screen happened to expose a lens picker
 * (TradeHubScreen's own pill row, PlayersScreen's own pill row), so picking
 * "Rebuild" on one screen left every other screen either stuck on its own
 * default or asking again from scratch. modules/*'s lens param is already
 * accepted on most league read endpoints (rankings, waivers, matchup, my
 * team, draft center, draft picks, player rank) — this context is what
 * finally lets every screen agree on the same chosen value for it.
 *
 * Client-only (no server persistence, unlike GM Stance): there's no backend
 * "saved lens" concept today, so this simply resets to DEFAULT_LENS on a
 * fresh app launch, same as every screen's own local default already did.
 */
export function ValuationLensProvider({ children }: { children: React.ReactNode }) {
  const [lenses, setLenses] = useState<Record<string, ValuationLens>>({});

  const getLens = useCallback((leagueId: string) => lenses[leagueId] ?? DEFAULT_LENS, [lenses]);

  const setLens = useCallback((leagueId: string, lens: ValuationLens) => {
    setLenses((prev) => ({ ...prev, [leagueId]: lens }));
  }, []);

  const value = useMemo<ValuationLensContextValue>(() => ({ getLens, setLens }), [getLens, setLens]);

  return <ValuationLensContext.Provider value={value}>{children}</ValuationLensContext.Provider>;
}

function useValuationLensContext(): ValuationLensContextValue {
  const context = useContext(ValuationLensContext);
  if (!context) {
    throw new Error('useValuationLens must be used within a ValuationLensProvider');
  }
  return context;
}

/** One league's evaluation lens, shared across every screen reading it. */
export function useValuationLens(leagueId: string) {
  const context = useValuationLensContext();
  const lens = context.getLens(leagueId);

  return {
    lens,
    setLens: useCallback((next: ValuationLens) => context.setLens(leagueId, next), [context, leagueId]),
  };
}
