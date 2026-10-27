import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { api } from '../lib/api';
import {
  experienceCopy,
  levelForTier,
  normalizeExperienceLevel,
  normalizeExperienceTier,
  normalizePrimaryGoal,
  tierForLevel,
  type ExperienceCopy,
  type ExperienceLevel,
  type ExperienceLevelSetting,
  type ExperienceTier,
  type ExperienceTierSetting,
  type PrimaryGoal,
  type PrimaryGoalSetting,
} from '../lib/experienceCopy';

const KEY = 'fgl:experience-level';
const TIER_KEY = 'fgl:experience-tier';
const GOAL_KEY = 'fgl:primary-goal';

interface Profile {
  level: ExperienceLevelSetting;
  tier: ExperienceTierSetting;
  goal: PrimaryGoalSetting;
}

interface ExperienceLevelContextValue {
  /** Legacy two-value level (drives the copy). Always consistent with `tier`. */
  level: ExperienceLevelSetting;
  tier: ExperienceTierSetting;
  /** Optional onboarding goal. Only ever used to suggest a Team Situation. */
  goal: PrimaryGoalSetting;
  /** Applies immediately, caches locally, and saves to /v1/preferences. If
   * the save fails the previous values are restored and the promise rejects
   * (callers may ignore it, as onboarding does). `goal: null` clears a stored
   * goal; leave it undefined to keep it. `persist: false` (guests) applies
   * and caches on this device only and never writes to the server. */
  setProfile: (
    profile: { tier: ExperienceTier; goal?: PrimaryGoal | null },
    options?: { persist?: boolean },
  ) => Promise<void>;
  /** Legacy single-value save (kept for existing callers). */
  setLevel: (level: ExperienceLevel) => Promise<void>;
  /** For AuthContext only: apply the durable /v1/preferences values (nulls
   * for an unanswered account, or after sign-out) without writing them back. */
  syncLevelFromServer: (level: ExperienceLevelSetting, tier?: ExperienceTierSetting, goal?: PrimaryGoalSetting) => void;
}

const ExperienceLevelContext = createContext<ExperienceLevelContextValue | undefined>(undefined);

/**
 * The account's onboarding answers: experience tier (new to fantasy / new to
 * dynasty / veteran), the legacy beginner/advanced level derived from it, and
 * an optional goal. Mirrors web-next's ExperienceLevelContext. Screens never
 * branch on it directly; they call useExperienceCopy(), which goes through
 * the central copy map in lib/experienceCopy.ts. Copy only, never features,
 * and null behaves exactly like "advanced" (today's copy). Independent of the
 * existing Guided/Compact density setting.
 */
export function ExperienceLevelProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfileState] = useState<Profile>({ level: null, tier: null, goal: null });
  const profileRef = useRef(profile);
  profileRef.current = profile;

  useEffect(() => {
    let cancelled = false;
    Promise.all([AsyncStorage.getItem(KEY), AsyncStorage.getItem(TIER_KEY), AsyncStorage.getItem(GOAL_KEY)])
      .then(([rawLevel, rawTier, rawGoal]) => {
        if (cancelled) return;
        const tier = normalizeExperienceTier(rawTier);
        const level = tier ? levelForTier(tier) : normalizeExperienceLevel(rawLevel);
        if (level) setProfileState({ level, tier: tier ?? tierForLevel(level), goal: normalizePrimaryGoal(rawGoal) });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const apply = (next: Profile) => {
    profileRef.current = next;
    setProfileState(next);
    const write = (key: string, value: string | null) =>
      (value ? AsyncStorage.setItem(key, value) : AsyncStorage.removeItem(key)).catch(() => {});
    write(KEY, next.level);
    write(TIER_KEY, next.tier);
    write(GOAL_KEY, next.goal);
  };

  const setProfile: ExperienceLevelContextValue['setProfile'] = async (next, options) => {
    const previous = profileRef.current;
    apply({
      level: levelForTier(next.tier),
      tier: next.tier,
      goal: next.goal === undefined ? previous.goal : next.goal,
    });
    if (options?.persist === false) return;
    try {
      await api.setExperienceProfile({
        tier: next.tier,
        goal: next.goal ?? null,
        clearGoal: next.goal === null && previous.goal !== null,
      });
    } catch (error) {
      // Roll back so the screen never shows a choice the server doesn't have.
      apply(previous);
      throw error;
    }
  };

  const setLevel = (next: ExperienceLevel) => {
    const current = profileRef.current;
    const tier = current.tier && levelForTier(current.tier) === next ? current.tier : tierForLevel(next);
    return setProfile({ tier });
  };

  const syncLevelFromServer = (
    level: ExperienceLevelSetting,
    tier: ExperienceTierSetting = null,
    goal: PrimaryGoalSetting = null,
  ) => {
    apply({ level, tier: tier ?? (level ? tierForLevel(level) : null), goal });
  };

  const value = useMemo<ExperienceLevelContextValue>(
    () => ({ level: profile.level, tier: profile.tier, goal: profile.goal, setProfile, setLevel, syncLevelFromServer }),
    // The setters only read refs, so they are stable for a given profile.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [profile],
  );

  return <ExperienceLevelContext.Provider value={value}>{children}</ExperienceLevelContext.Provider>;
}

/** Outside a provider this behaves as an unanswered account (today's copy). */
const FALLBACK: ExperienceLevelContextValue = {
  level: null,
  tier: null,
  goal: null,
  setProfile: async (next) => {
    await api.setExperienceProfile({ tier: next.tier, goal: next.goal ?? null });
  },
  setLevel: async (next) => {
    await api.setExperienceLevel(next);
  },
  syncLevelFromServer: () => {},
};

export function useExperienceLevel(): ExperienceLevelContextValue {
  return useContext(ExperienceLevelContext) ?? FALLBACK;
}

/** Copy helpers for the current account's experience level. */
export function useExperienceCopy(): ExperienceCopy {
  const { level, tier } = useExperienceLevel();
  return useMemo(() => experienceCopy(level, tier), [level, tier]);
}
