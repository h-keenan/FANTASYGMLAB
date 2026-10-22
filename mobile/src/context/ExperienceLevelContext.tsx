import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';
import {
  experienceCopy,
  normalizeExperienceLevel,
  type ExperienceCopy,
  type ExperienceLevel,
  type ExperienceLevelSetting,
} from '../lib/experienceCopy';

const KEY = 'fgl:experience-level';

interface ExperienceLevelContextValue {
  level: ExperienceLevelSetting;
  /** Applies immediately, caches locally, and saves to /v1/preferences
   * (best-effort, same as DensityContext.setDensity). */
  setLevel: (level: ExperienceLevel) => void;
  /** For AuthContext only: apply the durable /v1/preferences value (null
   * for an unanswered account, or after sign-out) without writing it back. */
  syncLevelFromServer: (level: ExperienceLevelSetting) => void;
}

const ExperienceLevelContext = createContext<ExperienceLevelContextValue | undefined>(undefined);

/**
 * The account's onboarding experience level ("beginner" | "advanced" |
 * null) — mirrors web-next's ExperienceLevelContext. Screens never branch on
 * it directly; they call useExperienceCopy(), which goes through the central
 * copy map in lib/experienceCopy.ts. Copy only, never features, and null
 * behaves exactly like "advanced" (today's copy). Independent of the
 * existing Guided/Compact density setting.
 */
export function ExperienceLevelProvider({ children }: { children: React.ReactNode }) {
  const [level, setLevelState] = useState<ExperienceLevelSetting>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        const cached = normalizeExperienceLevel(raw);
        if (cached) setLevelState(cached);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const writeCache = (next: ExperienceLevelSetting) => {
    (next ? AsyncStorage.setItem(KEY, next) : AsyncStorage.removeItem(KEY)).catch(() => {});
  };

  const setLevel = (next: ExperienceLevel) => {
    setLevelState(next);
    writeCache(next);
    api.setExperienceLevel(next).catch(() => {});
  };

  const syncLevelFromServer = (next: ExperienceLevelSetting) => {
    setLevelState(next);
    writeCache(next);
  };

  const value = useMemo<ExperienceLevelContextValue>(
    () => ({ level, setLevel, syncLevelFromServer }),
    [level],
  );

  return <ExperienceLevelContext.Provider value={value}>{children}</ExperienceLevelContext.Provider>;
}

/** Outside a provider this behaves as an unanswered account (today's copy). */
const FALLBACK: ExperienceLevelContextValue = {
  level: null,
  setLevel: (next) => {
    api.setExperienceLevel(next).catch(() => {});
  },
  syncLevelFromServer: () => {},
};

export function useExperienceLevel(): ExperienceLevelContextValue {
  return useContext(ExperienceLevelContext) ?? FALLBACK;
}

/** Copy helpers for the current account's experience level. */
export function useExperienceCopy(): ExperienceCopy {
  const { level } = useExperienceLevel();
  return useMemo(() => experienceCopy(level), [level]);
}
