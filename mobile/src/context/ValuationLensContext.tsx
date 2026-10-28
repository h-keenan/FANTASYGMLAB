import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { api, type ValuationLens } from '../lib/api';

export const DEFAULT_LENS: ValuationLens = 'Dynasty';

interface ValuationLensContextValue {
  getLens: (leagueId: string) => ValuationLens;
  setLens: (leagueId: string, lens: ValuationLens) => void;
  /** Fetch the league once and seed its default lens from the server. */
  ensureDetectedDefault: (leagueId: string) => void;
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
 * An explicit choice (setLens) is client-only and resets on a fresh launch.
 * The DEFAULT is not a blind 'Dynasty' any more: a redraft league defaulting
 * to a Dynasty-weighted lens was wrong (audit C6; web already detected it).
 * `ensureDetectedDefault` reads the server's `default_lens` from the league
 * payload (modules.league_value_settings.default_lens_for_league, the same
 * decision web and the push alerts use) once per league; best-effort, a
 * failed fetch just leaves DEFAULT_LENS.
 */
export function ValuationLensProvider({ children }: { children: React.ReactNode }) {
  const [lenses, setLenses] = useState<Record<string, ValuationLens>>({});
  const [detectedDefaults, setDetectedDefaults] = useState<Record<string, ValuationLens>>({});
  const attempted = useRef<Set<string>>(new Set());

  const getLens = useCallback(
    (leagueId: string) => lenses[leagueId] ?? detectedDefaults[leagueId] ?? DEFAULT_LENS,
    [lenses, detectedDefaults],
  );

  const ensureDetectedDefault = useCallback((leagueId: string) => {
    if (!leagueId || attempted.current.has(leagueId)) return;
    attempted.current.add(leagueId);
    api
      .getLeague(leagueId)
      .then((response) => {
        const detected: ValuationLens = response.default_lens === 'Non-Dynasty' ? 'Non-Dynasty' : 'Dynasty';
        setDetectedDefaults((prev) => (prev[leagueId] === detected ? prev : { ...prev, [leagueId]: detected }));
      })
      .catch(() => {
        // Best-effort: stays on DEFAULT_LENS. Allow a later retry.
        attempted.current.delete(leagueId);
      });
  }, []);

  const setLens = useCallback((leagueId: string, lens: ValuationLens) => {
    setLenses((prev) => ({ ...prev, [leagueId]: lens }));
  }, []);

  const value = useMemo<ValuationLensContextValue>(() => ({ getLens, setLens, ensureDetectedDefault }),
    [getLens, setLens, ensureDetectedDefault],);

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
  const { ensureDetectedDefault } = context;
  useEffect(() => {
    ensureDetectedDefault(leagueId);
  }, [ensureDetectedDefault, leagueId]);

  return {
    lens,
    setLens: useCallback((next: ValuationLens) => context.setLens(leagueId, next), [context, leagueId]),
  };
}
