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
  /** False until the lens is final for this load: an explicit choice, the
   * detected league type (remembered from an earlier visit, or fetched), or
   * a failed/slow detection. Pages hold their first fetch until then so a
   * redraft league's data isn't requested once as Dynasty and again as
   * Non-Dynasty. */
  isLensReady: (leagueId: string) => boolean;
  setLens: (leagueId: string, lens: ValuationLens) => void;
  ensureDetectedDefault: (leagueId: string) => void;
}

const DETECTED_LENS_STORAGE_KEY = "fgl.detectedLens.v1";
// Detection is one cached GET; never hold a page's first fetch longer than
// this if it hangs (the page then fetches with the default, as it always did).
export const LENS_DETECTION_MAX_WAIT_MS = 2500;

function readStoredLens(leagueId: string): ValuationLens | null {
  try {
    const raw = window.localStorage.getItem(DETECTED_LENS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
    const value = parsed?.[leagueId];
    return value === "Dynasty" || value === "Non-Dynasty" ? value : null;
  } catch {
    return null;
  }
}

function writeStoredLens(leagueId: string, lens: ValuationLens) {
  try {
    const raw = window.localStorage.getItem(DETECTED_LENS_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
    window.localStorage.setItem(DETECTED_LENS_STORAGE_KEY, JSON.stringify({ ...parsed, [leagueId]: lens }));
  } catch {
    /* private mode / quota: detection just isn't remembered */
  }
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
  const [settled, setSettled] = useState<Record<string, true>>({});
  const attempted = useRef<Set<string>>(new Set());

  const ensureDetectedDefault = useCallback((leagueId: string) => {
    if (!leagueId || attempted.current.has(leagueId)) return;
    attempted.current.add(leagueId);
    const settle = () => setSettled((prev) => (prev[leagueId] ? prev : { ...prev, [leagueId]: true }));
    // A league's type doesn't change, so what an earlier visit detected is
    // the right lens for this load's first fetch; the request below still
    // confirms it (and corrects it in the rare case it changed).
    const remembered = readStoredLens(leagueId);
    if (remembered) setDetectedDefaults((prev) => (prev[leagueId] ? prev : { ...prev, [leagueId]: remembered }));
    const timer = setTimeout(settle, LENS_DETECTION_MAX_WAIT_MS);
    api
      .getLeague(leagueId)
      .then(({ league }) => {
        // Sleeper: 0 = redraft, 1 = keeper, 2 = dynasty. Keepers share
        // dynasty horizon math (same as the server-side mapping), so only
        // a real redraft league gets the Redraft default.
        const detected: ValuationLens = league?.settings?.type === 0 ? "Non-Dynasty" : "Dynasty";
        writeStoredLens(leagueId, detected);
        setDetectedDefaults((prev) => (prev[leagueId] === detected ? prev : { ...prev, [leagueId]: detected }));
      })
      .catch(() => {
        // Best-effort — stays on DEFAULT_LENS if detection fails.
      })
      .finally(() => {
        clearTimeout(timer);
        settle();
      });
  }, []);

  const getLens = useCallback(
    (leagueId: string) => lenses[leagueId] ?? detectedDefaults[leagueId] ?? DEFAULT_LENS,
    [lenses, detectedDefaults],
  );
  const isLensReady = useCallback(
    (leagueId: string) => !leagueId || Boolean(lenses[leagueId] || detectedDefaults[leagueId] || settled[leagueId]),
    [lenses, detectedDefaults, settled],
  );
  const setLens = useCallback((leagueId: string, lens: ValuationLens) => {
    setLenses((prev) => ({ ...prev, [leagueId]: lens }));
  }, []);

  const value = useMemo<ValuationLensContextValue>(
    () => ({ getLens, isLensReady, setLens, ensureDetectedDefault }),
    [getLens, isLensReady, setLens, ensureDetectedDefault],
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
  const lensReady = context.isLensReady(leagueId);
  const setLens = useCallback((next: ValuationLens) => context.setLens(leagueId, next), [context, leagueId]);

  useEffect(() => {
    if (leagueId) context.ensureDetectedDefault(leagueId);
  }, [context, leagueId]);

  return { lens, setLens, lensReady };
}
