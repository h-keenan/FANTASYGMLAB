"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export const VALUATION_LENS_OPTIONS = [
  { value: "Dynasty", label: "Dynasty", hint: "Values future upside alongside this year." },
  { value: "Rebuild", label: "Rebuild", hint: "Weights youth and draft capital most heavily." },
  { value: "Non-Dynasty", label: "Redraft", hint: "Values this season only — future picks discounted." },
] as const;

export type ValuationLens = (typeof VALUATION_LENS_OPTIONS)[number]["value"];
export const DEFAULT_LENS: ValuationLens = "Dynasty";

interface ValuationLensContextValue {
  getLens: (leagueId: string) => ValuationLens;
  setLens: (leagueId: string, lens: ValuationLens) => void;
}

const ValuationLensContext = createContext<ValuationLensContextValue | undefined>(undefined);

/**
 * Port of mobile's ValuationLensContext — one shared, per-league evaluation
 * lens (Dynasty/Rebuild/Redraft) so every page reading it agrees on the
 * same chosen value, instead of each one defaulting to its own local
 * "Dynasty" guess the way every web-next page's api.ts call currently does
 * (coridian_, 2026-10-17: "the evaluation lens... similar to how the app
 * is" — this didn't exist anywhere in web-next before). Client-only, same
 * as mobile's: no server persistence, resets to DEFAULT_LENS on a fresh
 * page load.
 */
export function ValuationLensProvider({ children }: { children: ReactNode }) {
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
    throw new Error("useValuationLens must be used within a ValuationLensProvider");
  }
  return context;
}

/** One league's evaluation lens, shared across every page reading it. */
export function useValuationLens(leagueId: string) {
  const context = useValuationLensContext();
  const lens = context.getLens(leagueId);
  const setLens = useCallback((next: ValuationLens) => context.setLens(leagueId, next), [context, leagueId]);
  return { lens, setLens };
}
