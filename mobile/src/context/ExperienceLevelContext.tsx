import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { api } from '../lib/api';
import {
  experienceCopy,
  normalizeExperienceGoal,
  normalizeExperienceLevel,
  type ExperienceCopy,
  type ExperienceGoal,
  type ExperienceGoalSetting,
  type ExperienceLevel,
  type ExperienceLevelSetting,
} from '../lib/experienceCopy';

const KEY = 'fgl:experience-level';
const GOAL_KEY = 'fgl:experience-goal';

interface ExperienceLevelContextValue {
  level: ExperienceLevelSetting;
  /** Applies immediately, caches locally, and saves to /v1/preferences
   * (best-effort, same as DensityContext.setDensity). */
  setLevel: (level: ExperienceLevel) => void;
  /** For AuthContext only: apply the durable /v1/preferences value (null
   * for an unanswered account, or after sign-out) without writing it back. */
  syncLevelFromServer: (level: ExperienceLevelSetting) => void;
  goal: ExperienceGoalSetting;
  /** Applies immediately, caches locally, and saves to /v1/preferences
   * (best-effort). `null` clears it back to unset. */
  setGoal: (goal: ExperienceGoal | null) => void;
  /** For AuthContext only: apply the durable /v1/preferences value without
   * writing it back. */
  syncGoalFromServer: (goal: ExperienceGoalSetting) => void;
}

const ExperienceLevelContext = createContext<ExperienceLevelContextValue | undefined>(undefined);

/**
 * The account's onboarding experience level ("new_to_fantasy" | "beginner" |
 * "advanced" | null) and optional season goal — mirrors web-next's
 * ExperienceLevelContext. Screens never branch on level directly; they call
 * useExperienceCopy(), which goes through the central copy map in
 * lib/experienceCopy.ts. Copy only, never features, and null behaves
 * exactly like "advanced" (today's copy). Independent of the existing
 * Guided/Compact density setting.
 */
export function ExperienceLevelProvider({ children }: { children: React.ReactNode }) {
  const [level, setLevelState] = useState<ExperienceLevelSetting>(null);
  const [goal, setGoalState] = useState<ExperienceGoalSetting>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        const cached = normalizeExperienceLevel(raw);
        if (cached) setLevelState(cached);
      })
      .catch(() => {});
    AsyncStorage.getItem(GOAL_KEY)
      .then((raw) => {
        if (cancelled) return;
        const cached = normalizeExperienceGoal(raw);
        if (cached) setGoalState(cached);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const writeCache = (next: ExperienceLevelSetting) => {
    (next ? AsyncStorage.setItem(KEY, next) : AsyncStorage.removeItem(KEY)).catch(() => {});
  };

  const writeGoalCache = (next: ExperienceGoalSetting) => {
    (next ? AsyncStorage.setItem(GOAL_KEY, next) : AsyncStorage.removeItem(GOAL_KEY)).catch(() => {});
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

  const setGoal = (next: ExperienceGoal | null) => {
    setGoalState(next);
    writeGoalCache(next);
    api.setExperienceGoal(next).catch(() => {});
  };

  const syncGoalFromServer = (next: ExperienceGoalSetting) => {
    setGoalState(next);
    writeGoalCache(next);
  };

  const value = useMemo<ExperienceLevelContextValue>(
    () => ({ level, setLevel, syncLevelFromServer, goal, setGoal, syncGoalFromServer }),
    [level, goal],
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
  goal: null,
  setGoal: (next) => {
    api.setExperienceGoal(next).catch(() => {});
  },
  syncGoalFromServer: () => {},
};

export function useExperienceLevel(): ExperienceLevelContextValue {
  return useContext(ExperienceLevelContext) ?? FALLBACK;
}

/** Copy helpers for the current account's experience level. */
export function useExperienceCopy(): ExperienceCopy {
  const { level } = useExperienceLevel();
  return useMemo(() => experienceCopy(level), [level]);
}
