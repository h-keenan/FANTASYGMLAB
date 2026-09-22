import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';

import { api } from '../lib/api';
import { darkColors, lightColors, type ThemeColors } from '../theme';

export type ThemeMode = 'light' | 'dark' | 'auto';

const KEY = 'fgl:theme-mode';
// Matches every screen's pre-existing hardcoded behavior (the static
// `colors` export in theme.ts) until a screen migrates to `useThemeMode()`
// — changing this default would silently relight every unmigrated screen
// wrong, since only migrated screens can actually respond to the toggle.
const DEFAULT_MODE: ThemeMode = 'dark';

interface ThemeModeContextValue {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  /** Mode resolved against the OS setting when mode is "auto". */
  isDark: boolean;
  colors: ThemeColors;
  /** Same non-writeback pattern as DensityContext's syncDensityFromServer. */
  syncModeFromServer: (mode: ThemeMode) => void;
}

const ThemeModeContext = createContext<ThemeModeContextValue | undefined>(undefined);

/**
 * Day/Night/Auto theme toggle (direct request, 2026-09-22: OLED-black dark
 * theme + a "glacier ice white" light theme). Same cross-device shape as
 * DensityContext: an instant local AsyncStorage read, synced to the
 * durable /v1/preferences store (the same user_settings blob density/push
 * preferences already use) so it survives a reinstall or carries to a
 * second device.
 *
 * MIGRATION STATUS (2026-09-22): this provider and both palettes
 * (theme.ts's darkColors/lightColors) are real and complete, and the
 * Day/Night/Auto toggle in More actually persists and syncs — but most
 * screens still import the static `colors` export directly (always dark,
 * unchanged from before) rather than calling `useThemeMode()` here.
 * React Native bakes StyleSheet.create's values in at module-load time, so
 * there's no way to make an unmigrated screen theme-reactive without
 * touching that screen's own file — this is a real, tracked, one-screen-
 * at-a-time follow-up, not a gap in this provider. A screen has migrated
 * once it reads `colors` from this hook and builds its styles with
 * `useMemo(() => StyleSheet.create({...}), [colors])` instead of a
 * module-scope `StyleSheet.create`.
 */
export function ThemeModeProvider({ children }: { children: React.ReactNode }) {
  const systemScheme = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>(DEFAULT_MODE);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        if (raw === 'light' || raw === 'dark' || raw === 'auto') setModeState(raw);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setMode = (next: ThemeMode) => {
    setModeState(next);
    AsyncStorage.setItem(KEY, next).catch(() => {});
    api.updateDevicePreferences({ themeMode: next }).catch(() => {});
  };

  const syncModeFromServer = (next: ThemeMode) => {
    setModeState(next);
    AsyncStorage.setItem(KEY, next).catch(() => {});
  };

  const isDark = mode === 'auto' ? systemScheme !== 'light' : mode === 'dark';
  const activeColors = isDark ? darkColors : lightColors;

  const value = useMemo<ThemeModeContextValue>(
    () => ({ mode, setMode, isDark, colors: activeColors, syncModeFromServer }),
    [mode, isDark, activeColors],
  );

  return <ThemeModeContext.Provider value={value}>{children}</ThemeModeContext.Provider>;
}

export function useThemeMode(): ThemeModeContextValue {
  const context = useContext(ThemeModeContext);
  if (!context) {
    throw new Error('useThemeMode must be used within a ThemeModeProvider');
  }
  return context;
}
