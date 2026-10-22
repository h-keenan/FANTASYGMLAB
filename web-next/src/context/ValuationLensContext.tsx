"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api } from "@/lib/api";
import { DEFAULT_LENS, VALUATION_LENS_OPTIONS, type ValuationLens } from "@/lib/valuationLens";

export { DEFAULT_LENS, VALUATION_LENS_OPTIONS, type ValuationLens };

interface ValuationLensContextValue {
  getLens: (leagueId: string) => ValuationLens;
  setLens: (leagueId: string, lens: ValuationLens) => void;
  ensureDetectedDefault: (leagueId: string) => void;
}

const ValuationLensContext = createContext<ValuationLensContextValue | undefined>(undefined);

/**
 * Port of mobile's ValuationLensContext — one shared, per-league evaluation
 * lens (Dynasty/Rebuild/Redraft) so every page reading it agrees on the
 * same chosen value, instead of each one defaulting to its own local
 * "Dynasty" guess the way every web-next page's api.ts call currently did
 * (coridian_, 2026-10-17: "the evaluation lens... similar to how the app
 * is" — this didn't exist anywhere in web-next before). Client-only, same
 * as mobile's: no server persistence, resets to a fresh default on a new
 * page load — an explicit user choice (setLens) always wins over the
 * detected default below.
 *
 * Unlike mobile's version, the per-league DEFAULT isn't a blind "Dynasty"
 * either: a real Redraft league defaulting to a Dynasty-weighted valuation
 * lens is wrong, not just imprecise (coridian_: "it should always check to
 * see if the league is a dynasty or not. If it's redraft, it should not
 * automatically input that as dynasty"). `ensureDetectedDefault` fetches
 * the league's own real Sleeper `settings.type` once per league (0 =
 * redraft, 1 = keeper, 2 = dynasty — same mapping
 * modules.league_value_settings.detect_league_value_settings_from_payload
 * uses server-side) and seeds the default accordingly; best-effort — a
 * failed fetch just leaves DEFAULT_LENS in place, same as before.
 */
export function ValuationLensProvider({ children }: { children: ReactNode }) {
  const [lenses, setLenses] = useState<Record<string, ValuationLens>>({});
  const [detectedDefaults, setDetectedDefaults] = useState<Record<string, ValuationLens>>({});
  const attempted = useRef<Set<string>>(new Set());

  const ensureDetectedDefault = useCallback((leagueId: string) => {
    if (!leagueId || attempted.current.has(leagueId)) return;
    attempted.current.add(leagueId);
    api
      .getLeague(leagueId)
      .then(({ league }) => {
        // Sleeper: 0 = redraft, 1 = keeper, 2 = dynasty. Keepers share
        // dynasty horizon math (same as the server-side mapping), so only
        // a real redraft league gets the Redraft default.
        const detected: ValuationLens = league?.settings?.type === 0 ? "Non-Dynasty" : "Dynasty";
        setDetectedDefaults((prev) => (prev[leagueId] ? prev : { ...prev, [leagueId]: detected }));
      })
      .catch(() => {
        // Best-effort — stays on DEFAULT_LENS if detection fails.
      });
  }, []);

  const getLens = useCallback(
    (leagueId: string) => lenses[leagueId] ?? detectedDefaults[leagueId] ?? DEFAULT_LENS,
    [lenses, detectedDefaults],
  );
  const setLens = useCallback((leagueId: string, lens: ValuationLens) => {
    setLenses((prev) => ({ ...prev, [leagueId]: lens }));
  }, []);

  const value = useMemo<ValuationLensContextValue>(
    () => ({ getLens, setLens, ensureDetectedDefault }),
    [getLens, setLens, ensureDetectedDefault],
  );
  return <ValuationLensContext.Provider value={value}>{children}</ValuationLensContext.Provider>;
}

function useValuationLensContext(): ValuationLensContextValue {
  const context = useContext(ValuationLensContext);
  if (!context) {
    throw new Error("useValuationLens must be used within a ValuationLensProvider");
  }
  return context;
}

/** One league's evaluation lens, shared across every page reading it. */
export function useValuationLens(leagueId: string) {
  const context = useValuationLensContext();
  const lens = context.getLens(leagueId);
  const setLens = useCallback((next: ValuationLens) => context.setLens(leagueId, next), [context, leagueId]);

  useEffect(() => {
    if (leagueId) context.ensureDetectedDefault(leagueId);
  }, [context, leagueId]);

  return { lens, setLens };
}
