import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { api, teamStrategyForStance, type TeamStance, type TeamStrategy } from '../lib/api';

interface StanceEntry {
  /** Raw Team Situation declaration — '' when nothing's been declared yet. */
  stance: TeamStance | '';
  /** Mapped via teamStrategyForStance — what the real age-curve valuation
   * math (and every screen that predates this merge) actually consumes. */
  strategy: TeamStrategy;
  isSet: boolean;
}

/** What the app shows while nothing has been declared — teamStrategyForStance('')'s
 * own fallback, and what every pre-merge caller of this context already
 * expected as the "nothing chosen" default. */
export const AUTO_STRATEGY: TeamStrategy = 'retool';

interface GmStanceContextValue {
  /** Undefined until a first load resolves for this league. */
  getStance: (leagueId: string) => StanceEntry | undefined;
  /** Fetch-or-return-cached; safe to call from multiple screens at once — a
   * single in-flight request is shared rather than one per caller. */
  loadStance: (leagueId: string) => Promise<StanceEntry>;
  /** Optimistic local update + best-effort persist, mirrored to every
   * screen reading this league's stance through the context. */
  setStance: (leagueId: string, stance: TeamStance) => void;
}

const GmStanceContext = createContext<GmStanceContextValue | undefined>(undefined);

/**
 * GM Stance / Team Situation merge (product decision, 2026-09-26): this
 * context used to read/write a SEPARATE, five-state GM Stance value
 * ("evaluation lens" in coridian_'s words) via getGmStance/updateGmStance,
 * backed by its own now-retired storage. It now reads/writes Team
 * Situation directly (getTeamStance/setTeamStance — the SAME store
 * TeamStanceScreen's "Team Situation" screen uses) and derives the
 * `strategy` value every pre-merge screen already expects via
 * teamStrategyForStance, so those screens don't need to change at all.
 *
 * Team Situation has no "unset"/"Reset to Auto" concept (unlike the old GM
 * Stance control) — a league with nothing declared just reports
 * isSet=false and the default-fallback `strategy`, same as before.
 *
 * Lifted into one shared, per-league cache (rather than one local
 * `useState` per screen) because React Navigation reuses an
 * already-mounted screen instance rather than remounting it on revisit —
 * changing stance on one screen would otherwise leave every other
 * already-visited screen holding a stale copy: "it doesn't know what the
 * current lens is... conflict between two different pages" (coridian_).
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
      .getTeamStance(leagueId)
      .then((result) => {
        const stance = result.stance || '';
        const entry: StanceEntry = { stance, strategy: teamStrategyForStance(stance), isSet: Boolean(stance) };
        setStances((prev) => ({ ...prev, [leagueId]: entry }));
        return entry;
      })
      .catch(() => {
        const fallback: StanceEntry = { stance: '', strategy: AUTO_STRATEGY, isSet: false };
        setStances((prev) => ({ ...prev, [leagueId]: fallback }));
        return fallback;
      })
      .finally(() => {
        delete inFlight.current[leagueId];
      });
    inFlight.current[leagueId] = request;
    return request;
  }, []);

  const setStance = useCallback((leagueId: string, stance: TeamStance) => {
    setStances((prev) => ({ ...prev, [leagueId]: { stance, strategy: teamStrategyForStance(stance), isSet: true } }));
    void api.setTeamStance(leagueId, stance).catch(() => {});
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
    stance: entry?.stance ?? '',
    strategy: entry?.strategy ?? AUTO_STRATEGY,
    isSet: entry?.isSet ?? true,
    loaded: entry !== undefined,
    setStance: useCallback((next: TeamStance) => context.setStance(leagueId, next), [context, leagueId]),
  };
}
