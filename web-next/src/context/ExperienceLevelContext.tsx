"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
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
} from "@/lib/experienceCopy";

interface Stored {
  userId: string | null;
  level: ExperienceLevelSetting;
  tier: ExperienceTierSetting;
  goal: PrimaryGoalSetting;
  /** True once the server has answered for this user. */
  loaded: boolean;
}

interface ExperienceLevelContextValue {
  /** Legacy two-value level (drives the copy). Always consistent with `tier`. */
  level: ExperienceLevelSetting;
  tier: ExperienceTierSetting;
  /** Optional onboarding goal. Only ever used to suggest a Team Situation. */
  goal: PrimaryGoalSetting;
  /** Saves the tier (and optionally a goal) through POST /v1/preferences and
   * applies immediately. `goal: null` clears a stored goal; leave it
   * undefined to keep it. Rejects (and restores the previous values) when
   * the write fails. Signed-out visitors are never stored. */
  setProfile: (profile: { tier: ExperienceTier; goal?: PrimaryGoal | null }) => Promise<void>;
  /** Legacy single-value save (kept for existing callers). */
  setLevel: (level: ExperienceLevel) => Promise<void>;
}

const ExperienceLevelContext = createContext<ExperienceLevelContextValue | undefined>(undefined);

const EMPTY: Stored = { userId: null, level: null, tier: null, goal: null, loaded: false };

/**
 * The signed-in account's onboarding answers: the experience tier (new to
 * fantasy / new to dynasty / veteran), the legacy beginner/advanced level
 * derived from it, and an optional goal. Read from the durable user_settings
 * store via GET /v1/preferences once a session exists. Pages never branch on
 * it directly: they call useExperienceCopy(), which goes through the central
 * copy map in lib/experienceCopy.ts. Copy only, never features. null behaves
 * exactly like "advanced".
 */
export function ExperienceLevelProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? null;
  // Stored with the user it belongs to, so a sign-out or account switch
  // falls back to nothing without a reset inside the effect.
  const [stored, setStored] = useState<Stored>(EMPTY);
  const current: Stored = userId && stored.userId === userId ? stored : EMPTY;
  // A choice made in this session (onboarding, Account page) wins over a
  // GET that was still in flight when it was made. Holds the user id the
  // choice was made for.
  const chosenFor = useRef<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    api
      .getDevicePreferences()
      .then((result) => {
        if (cancelled || !result.ok || chosenFor.current === userId) return;
        setStored({
          userId,
          level: normalizeExperienceLevel(result.experience_level),
          tier: normalizeExperienceTier(result.experience_tier),
          goal: normalizePrimaryGoal(result.primary_goal),
          loaded: true,
        });
      })
      .catch(() => {
        // Best-effort: a failed read leaves the default (advanced) copy.
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setProfile = useCallback(
    async (profile: { tier: ExperienceTier; goal?: PrimaryGoal | null }) => {
      // Guests and signed-out visitors: nothing is stored.
      if (!userId) return;
      const previous = current;
      chosenFor.current = userId;
      const nextGoal = profile.goal === undefined ? previous.goal : profile.goal;
      setStored({ userId, level: levelForTier(profile.tier), tier: profile.tier, goal: nextGoal, loaded: true });
      try {
        await api.setExperienceProfile({
          tier: profile.tier,
          goal: profile.goal ?? null,
          clearGoal: profile.goal === null && previous.goal !== null,
        });
      } catch (error) {
        setStored({ ...previous, userId });
        throw error;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [userId, current.level, current.tier, current.goal, current.loaded],
  );

  const setLevel = useCallback(
    (next: ExperienceLevel) => {
      // Keep a finer tier when it already agrees with the level.
      const tier = current.tier && levelForTier(current.tier) === next ? current.tier : tierForLevel(next);
      return setProfile({ tier });
    },
    [current.tier, setProfile],
  );

  const value = useMemo<ExperienceLevelContextValue>(
    () => ({ level: current.level, tier: current.tier, goal: current.goal, setProfile, setLevel }),
    [current.level, current.tier, current.goal, setProfile, setLevel],
  );
  return <ExperienceLevelContext.Provider value={value}>{children}</ExperienceLevelContext.Provider>;
}

/** Outside a provider (isolated component tests, static pages) this acts as
 * an unanswered account, so today's copy renders, and saves still go through. */
const FALLBACK: ExperienceLevelContextValue = {
  level: null,
  tier: null,
  goal: null,
  setProfile: async (profile) => {
    await api.setExperienceProfile({ tier: profile.tier, goal: profile.goal ?? null });
  },
  setLevel: async (next) => {
    await api.setExperienceLevel(next);
  },
};

export function useExperienceLevel(): ExperienceLevelContextValue {
  return useContext(ExperienceLevelContext) ?? FALLBACK;
}

/** The copy helpers for the current account's experience level. */
export function useExperienceCopy(): ExperienceCopy {
  const { level, tier } = useExperienceLevel();
  return useMemo(() => experienceCopy(level, tier), [level, tier]);
}
