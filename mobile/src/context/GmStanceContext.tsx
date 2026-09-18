import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { api, type TeamStrategy } from '../lib/api';

interface StanceEntry {
  strategy: TeamStrategy;
  isSet: boolean;
}

interface GmStanceContextValue {
  /** Undefined until a first load resolves for this league. */
  getStance: (leagueId: string) => StanceEntry | undefined;
  /** Fetch-or-return-cached; safe to call from multiple screens at once — a
   * single in-flight request is shared rather than one per caller. */
  loadStance: (leagueId: string) => Promise<StanceEntry>;
  /** Optimistic local update + best-effort persist, mirrored to every
   * screen reading this league's stance through the context. */
  setStance: (leagueId: string, strategy: TeamStrategy) => void;
}

const GmStanceContext = createContext<GmStanceContextValue | undefined>(undefined);

/**
 * GM Stance ("evaluation lens" in coridian_'s words) used to be three
 * independent copies of local `useState`, one each in LeagueDetailScreen,
 * TradeHubScreen, and TradeAnalyzerScreen — each fetched once on its own
 * mount and never refetched. React Navigation reuses an already-mounted
 * screen instance rather than remounting it on revisit, so changing stance
 * on one screen left every other already-visited screen holding a stale
 * copy: "it doesn't know what the current lens is... conflict between two
 * different pages." This lifts stance into one shared, per-league cache —
 * following DensityContext's fetch-once/set/persist shape — so a write
 * from any screen is immediately visible to every other screen reading the
 * same league's stance, without each one polling or refetching.
 */
export function GmStanceProvider({ children }: { children: React.ReactNode }) {
  const [stances, setStances] = useState<Record<string, StanceEntry>>({});
  const stancesRef = useRef(stances);
  stancesRef.current = stances;
  const inFlight = useRef<Record<string, Promise<StanceEntry>>>({});

  const getStance = useCallback((leagueId: string) => stancesRef.current[leagueId], []);

  const loadStance = useCallback((leagueId: string): Promise<StanceEntry> => {
    const cached = stancesRef.current[leagueId];
    if (cached) return Promise.resolve(cached);
    const pending = inFlight.current[leagueId];
    if (pending) return pending;

    const request = api
      .getGmStance(leagueId)
      .then((result) => {
        const entry: StanceEntry = { strategy: result.strategy, isSet: result.is_set ?? true };
        setStances((prev) => ({ ...prev, [leagueId]: entry }));
        return entry;
      })
      .catch(() => {
        const fallback: StanceEntry = { strategy: 'retool', isSet: false };
        setStances((prev) => ({ ...prev, [leagueId]: fallback }));
        return fallback;
      })
      .finally(() => {
        delete inFlight.current[leagueId];
      });
    inFlight.current[leagueId] = request;
    return request;
  }, []);

  const setStance = useCallback((leagueId: string, strategy: TeamStrategy) => {
    setStances((prev) => ({ ...prev, [leagueId]: { strategy, isSet: true } }));
    void api.updateGmStance(leagueId, strategy).catch(() => {});
  }, []);

  const value = useMemo<GmStanceContextValue>(
    () => ({ getStance, loadStance, setStance }),
    [getStance, loadStance, setStance],
  );

  return <GmStanceContext.Provider value={value}>{children}</GmStanceContext.Provider>;
}

function useGmStanceContext(): GmStanceContextValue {
  const context = useContext(GmStanceContext);
  if (!context) {
    throw new Error('useGmStance must be used within a GmStanceProvider');
  }
  return context;
}

/** One league's stance, kicking off a load on first use and re-rendering
 * this screen whenever any screen changes it. */
export function useGmStance(leagueId: string) {
  const context = useGmStanceContext();
  const entry = context.getStance(leagueId);

  useEffect(() => {
    void context.loadStance(leagueId);
  }, [context, leagueId]);

  return {
    strategy: entry?.strategy ?? 'retool',
    isSet: entry?.isSet ?? true,
    loaded: entry !== undefined,
    setStrategy: useCallback((next: TeamStrategy) => context.setStance(leagueId, next), [context, leagueId]),
  };
}
