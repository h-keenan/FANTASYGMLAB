/**
 * Display preferences shared by the Account page and the rest of the web
 * app: density (Guided/Compact), theme (Night/Day/Auto) and the college
 * football interest switch. Mirrors the app (mobile DensityContext,
 * ThemeModeContext, CollegeInterestContext and the MoreScreen option
 * copy), and density/theme use the same durable /v1/preferences fields
 * (ui_density, theme_mode), so a choice made in one place follows the
 * account to the other. Pure TS, no DOM access.
 */

export type UiDensity = "guided" | "compact";
export type ThemeMode = "light" | "dark" | "auto";
export type CollegeInterest = "on" | "off";

export const DENSITY_STORAGE_KEY = "fgl:ui-density";
export const THEME_STORAGE_KEY = "fgl:theme-mode";
export const COLLEGE_INTEREST_STORAGE_KEY = "fgl:college-football-interest-web";

export const DEFAULT_DENSITY: UiDensity = "guided";
/** Web follows the visitor's system setting until they pick one (the app
 * defaults to dark; web already behaved as "auto" before this existed). */
export const DEFAULT_THEME_MODE: ThemeMode = "auto";
/** Web already showed College Scouting everywhere; "on" keeps that. */
export const DEFAULT_COLLEGE_INTEREST: CollegeInterest = "on";

/** Same labels and descriptions as mobile MoreScreen's DENSITY_OPTIONS. */
export const DENSITY_OPTIONS: Array<{ value: UiDensity; label: string; description: string }> = [
  { value: "guided", label: "Guided", description: "Show the reasoning behind every recommendation" },
  { value: "compact", label: "Compact", description: "Just the calls, hide the explanation text" },
];

/** Same labels and descriptions as mobile MoreScreen's THEME_OPTIONS. */
export const THEME_OPTIONS: Array<{ value: ThemeMode; label: string; description: string }> = [
  { value: "dark", label: "Night", description: "OLED black, always dark" },
  { value: "light", label: "Day", description: "Glacier ice white, always light" },
  { value: "auto", label: "Auto", description: "Match this device's system setting" },
];

export function normalizeDensity(value: unknown): UiDensity | null {
  return value === "guided" || value === "compact" ? value : null;
}

export function normalizeThemeMode(value: unknown): ThemeMode | null {
  return value === "light" || value === "dark" || value === "auto" ? value : null;
}

export function normalizeCollegeInterest(value: unknown): CollegeInterest | null {
  return value === "on" || value === "off" ? value : null;
}

/** The `data-theme` attribute value for a mode: "auto" sets none so the
 * `prefers-color-scheme` rules in globals.css decide. */
export function themeAttribute(mode: ThemeMode): "light" | "dark" | null {
  return mode === "auto" ? null : mode;
}

/**
 * Runs in <head> before first paint so a forced Day/Night choice never
 * flashes the system theme. Must stay in sync with THEME_STORAGE_KEY and
 * themeAttribute (a unit test pins both).
 */
export const THEME_BOOT_SCRIPT =
  '(function(){try{var t=localStorage.getItem("' +
  THEME_STORAGE_KEY +
  '");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t)}}catch(e){}})();';
