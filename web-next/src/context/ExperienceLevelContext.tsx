"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  experienceCopy,
  normalizeExperienceLevel,
  type ExperienceCopy,
  type ExperienceLevel,
  type ExperienceLevelSetting,
} from "@/lib/experienceCopy";

interface ExperienceLevelContextValue {
  level: ExperienceLevelSetting;
  /** Saves through POST /v1/preferences and applies immediately. Rejects
   * (and restores the previous value) when the write fails. */
  setLevel: (level: ExperienceLevel) => Promise<void>;
}

const ExperienceLevelContext = createContext<ExperienceLevelContextValue | undefined>(undefined);

/**
 * The signed-in account's onboarding experience level ("beginner",
 * "advanced", or null when it was never answered), read from the durable
 * user_settings store via GET /v1/preferences once a session exists.
 * Pages never branch on it directly: they call useExperienceCopy(), which
 * goes through the central copy map in lib/experienceCopy.ts. Copy only,
 * never features. null behaves exactly like "advanced".
 */
export function ExperienceLevelProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? null;
  // Stored with the user it belongs to, so a sign-out or account switch
  // falls back to null (advanced) without a reset inside the effect.
  const [stored, setStored] = useState<{ userId: string | null; level: ExperienceLevelSetting }>({
    userId: null,
    level: null,
  });
  const level = userId && stored.userId === userId ? stored.level : null;
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
        setStored({ userId, level: normalizeExperienceLevel(result.experience_level) });
      })
      .catch(() => {
        // Best-effort: a failed read leaves the default (advanced) copy.
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const setLevel = useCallback(
    async (next: ExperienceLevel) => {
      const previous = level;
      chosenFor.current = userId;
      setStored({ userId, level: next });
      try {
        await api.setExperienceLevel(next);
      } catch (error) {
        setStored({ userId, level: previous });
        throw error;
      }
    },
    [level, userId],
  );

  const value = useMemo<ExperienceLevelContextValue>(() => ({ level, setLevel }), [level, setLevel]);
  return <ExperienceLevelContext.Provider value={value}>{children}</ExperienceLevelContext.Provider>;
}

/** Outside a provider (isolated component tests, static pages) this acts as
 * an unanswered account, so today's copy renders, and setLevel still saves. */
const FALLBACK: ExperienceLevelContextValue = {
  level: null,
  setLevel: async (next) => {
    await api.setExperienceLevel(next);
  },
};

export function useExperienceLevel(): ExperienceLevelContextValue {
  return useContext(ExperienceLevelContext) ?? FALLBACK;
}

/** The copy helpers for the current account's experience level. */
export function useExperienceCopy(): ExperienceCopy {
  const { level } = useExperienceLevel();
  return useMemo(() => experienceCopy(level), [level]);
}
