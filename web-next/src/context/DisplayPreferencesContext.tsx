"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  COLLEGE_INTEREST_STORAGE_KEY,
  DEFAULT_COLLEGE_INTEREST,
  DEFAULT_DENSITY,
  DEFAULT_THEME_MODE,
  DENSITY_STORAGE_KEY,
  THEME_STORAGE_KEY,
  normalizeCollegeInterest,
  normalizeDensity,
  normalizeThemeMode,
  themeAttribute,
  type CollegeInterest,
  type ThemeMode,
  type UiDensity,
} from "@/lib/displayPreferences";

interface DisplayPreferencesValue {
  density: UiDensity;
  /** True when "why" / explanation copy should render (Guided). */
  showExplanations: boolean;
  setDensity: (density: UiDensity) => void;
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  /** "off" hides College Scouting from navigation; the page still works by URL. */
  collegeInterest: CollegeInterest;
  setCollegeInterest: (interest: CollegeInterest) => void;
}

// Components rendered outside the provider (unit tests, isolated pages) get
// the defaults instead of a throw, same as a first-time visitor.
const FALLBACK: DisplayPreferencesValue = {
  density: DEFAULT_DENSITY,
  showExplanations: true,
  setDensity: () => {},
  themeMode: DEFAULT_THEME_MODE,
  setThemeMode: () => {},
  collegeInterest: DEFAULT_COLLEGE_INTEREST,
  setCollegeInterest: () => {},
};

const DisplayPreferencesContext = createContext<DisplayPreferencesValue | undefined>(undefined);

function readStored<T>(key: string, normalize: (value: unknown) => T | null): T | null {
  try {
    return normalize(window.localStorage.getItem(key));
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode / blocked storage: the choice still applies this session.
  }
}

function applyTheme(mode: ThemeMode) {
  const attribute = themeAttribute(mode);
  if (attribute) document.documentElement.setAttribute("data-theme", attribute);
  else document.documentElement.removeAttribute("data-theme");
}

/**
 * Density, theme and college-interest preferences. Local storage gives an
 * instant read (and powers the pre-paint theme script); density and theme
 * also sync through the durable /v1/preferences store the app uses, so a
 * choice follows the account across devices and platforms. The server
 * reports `theme_mode_set` so an account that never picked a theme keeps
 * following the system setting instead of adopting the app's "dark" fallback.
 * College interest is per-browser, like the app's.
 */
export function DisplayPreferencesProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? null;
  const [density, setDensityState] = useState<UiDensity>(DEFAULT_DENSITY);
  const [themeMode, setThemeModeState] = useState<ThemeMode>(DEFAULT_THEME_MODE);
  const [collegeInterest, setCollegeInterestState] = useState<CollegeInterest>(DEFAULT_COLLEGE_INTEREST);
  // A choice made this session wins over a GET still in flight.
  const chosen = useRef({ density: false, theme: false });

  useEffect(() => {
    // Local storage is only readable after mount, so state is seeded here
    // rather than in useState initializers (which would mismatch SSR).
    /* eslint-disable react-hooks/set-state-in-effect */
    const storedDensity = readStored(DENSITY_STORAGE_KEY, normalizeDensity);
    if (storedDensity) setDensityState(storedDensity);
    const storedTheme = readStored(THEME_STORAGE_KEY, normalizeThemeMode);
    if (storedTheme) setThemeModeState(storedTheme);
    const storedCollege = readStored(COLLEGE_INTEREST_STORAGE_KEY, normalizeCollegeInterest);
    if (storedCollege) setCollegeInterestState(storedCollege);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    api
      .getDevicePreferences()
      .then((result) => {
        if (cancelled || !result.ok) return;
        const serverDensity = normalizeDensity(result.ui_density);
        if (serverDensity && !chosen.current.density) {
          setDensityState(serverDensity);
          writeStored(DENSITY_STORAGE_KEY, serverDensity);
        }
        const serverTheme = normalizeThemeMode(result.theme_mode);
        if (serverTheme && result.theme_mode_set && !chosen.current.theme) {
          setThemeModeState(serverTheme);
          writeStored(THEME_STORAGE_KEY, serverTheme);
          applyTheme(serverTheme);
        }
      })
      .catch(() => {
        // Best-effort: a failed read keeps the local value.
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setDensity = useCallback(
    (next: UiDensity) => {
      chosen.current.density = true;
      setDensityState(next);
      writeStored(DENSITY_STORAGE_KEY, next);
      if (userId) api.updateDevicePreferences({ ui_density: next }).catch(() => {});
    },
    [userId],
  );

  const setThemeMode = useCallback(
    (next: ThemeMode) => {
      chosen.current.theme = true;
      setThemeModeState(next);
      writeStored(THEME_STORAGE_KEY, next);
      applyTheme(next);
      if (userId) api.updateDevicePreferences({ theme_mode: next }).catch(() => {});
    },
    [userId],
  );

  const setCollegeInterest = useCallback((next: CollegeInterest) => {
    setCollegeInterestState(next);
    writeStored(COLLEGE_INTEREST_STORAGE_KEY, next);
  }, []);

  const value = useMemo<DisplayPreferencesValue>(
    () => ({
      density,
      showExplanations: density === "guided",
      setDensity,
      themeMode,
      setThemeMode,
      collegeInterest,
      setCollegeInterest,
    }),
    [density, setDensity, themeMode, setThemeMode, collegeInterest, setCollegeInterest],
  );

  return <DisplayPreferencesContext.Provider value={value}>{children}</DisplayPreferencesContext.Provider>;
}

export function useDisplayPreferences(): DisplayPreferencesValue {
  return useContext(DisplayPreferencesContext) ?? FALLBACK;
}
