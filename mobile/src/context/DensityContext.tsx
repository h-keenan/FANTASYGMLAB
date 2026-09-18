import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';

export type UiDensity = 'guided' | 'compact';

const KEY = 'fgl:ui-density';
const DEFAULT_DENSITY: UiDensity = 'guided';

interface DensityContextValue {
  density: UiDensity;
  setDensity: (density: UiDensity) => void;
  /** Convenience: true when "why"/explanation copy should render. */
  showExplanations: boolean;
  /**
   * For AuthContext only: apply a value fetched from the durable
   * /v1/preferences store without re-writing it back (avoids a redundant
   * round trip and can't loop). Local-only signed-out use never calls this.
   */
  syncDensityFromServer: (density: UiDensity) => void;
}

const DensityContext = createContext<DensityContextValue | undefined>(undefined);

/**
 * Beginner ("guided") vs. power-user ("compact") density — the web app's
 * own answer to "someone new to fantasy football and a power user both
 * need this to work" is showing "why"/confidence-reasoning copy by default
 * and letting it be collapsed (e.g. "How this board is ranked" expanders in
 * modules/trade_hub_ui.py). Mobile didn't have an equivalent toggle; this
 * is a per-device preference cached in AsyncStorage for instant reads, and
 * also synced to the durable /v1/preferences store (the same user_settings
 * blob push-category preferences already use) so it survives a reinstall
 * or carries to a second device — AuthContext calls syncDensityFromServer
 * once a session is established. Applied to the Dashboard's reason text as
 * the first concrete usage; other screens can adopt the same
 * `showExplanations` flag as a follow-up.
 */
export function DensityProvider({ children }: { children: React.ReactNode }) {
  const [density, setDensityState] = useState<UiDensity>(DEFAULT_DENSITY);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        if (raw === 'guided' || raw === 'compact') setDensityState(raw);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const setDensity = (next: UiDensity) => {
    setDensityState(next);
    AsyncStorage.setItem(KEY, next).catch(() => {});
    api.updateDevicePreferences({ uiDensity: next }).catch(() => {});
  };

  const syncDensityFromServer = (next: UiDensity) => {
    setDensityState(next);
    AsyncStorage.setItem(KEY, next).catch(() => {});
  };

  const value = useMemo<DensityContextValue>(
    () => ({ density, setDensity, showExplanations: density === 'guided', syncDensityFromServer }),
    [density],
  );

  return <DensityContext.Provider value={value}>{children}</DensityContext.Provider>;
}

export function useDensity(): DensityContextValue {
  const context = useContext(DensityContext);
  if (!context) {
    throw new Error('useDensity must be used within a DensityProvider');
  }
  return context;
}
