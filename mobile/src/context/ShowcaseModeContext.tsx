import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';

const KEY = 'fgl:showcase-mode';

interface ShowcaseModeContextValue {
  showcaseMode: boolean;
  setShowcaseMode: (enabled: boolean) => void;
}

const ShowcaseModeContext = createContext<ShowcaseModeContextValue | undefined>(undefined);

/**
 * Dev-only recording mode (see lib/showcaseMode.ts). Shaped like
 * DensityContext — AsyncStorage-backed boolean behind a hook — but
 * deliberately local-only: there's no /v1/preferences sync, because this is
 * a per-device recording switch for one dev handset, not a preference that
 * should follow the account to a second device or survive a reinstall on a
 * reviewer's phone. It IS persisted so a mid-recording app restart (or a
 * crash while filming) doesn't silently unmask a real league on camera.
 *
 * The effect below is what actually arms the masking: `lib/api.ts` is a
 * plain module and can't read context, so the flag is mirrored into a
 * module-level variable it checks before returning any response body.
 */
export function ShowcaseModeProvider({ children }: { children: React.ReactNode }) {
  const [showcaseMode, setShowcaseModeState] = useState(false);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        if (raw === '1') setShowcaseModeState(true);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    api.setShowcaseModeEnabled(showcaseMode);
  }, [showcaseMode]);

  const setShowcaseMode = (next: boolean) => {
    setShowcaseModeState(next);
    AsyncStorage.setItem(KEY, next ? '1' : '0').catch(() => {});
  };

  const value = useMemo<ShowcaseModeContextValue>(
    () => ({ showcaseMode, setShowcaseMode }),
    [showcaseMode],
  );

  return <ShowcaseModeContext.Provider value={value}>{children}</ShowcaseModeContext.Provider>;
}

export function useShowcaseMode(): ShowcaseModeContextValue {
  const context = useContext(ShowcaseModeContext);
  if (!context) {
    throw new Error('useShowcaseMode must be used within a ShowcaseModeProvider');
  }
  return context;
}
