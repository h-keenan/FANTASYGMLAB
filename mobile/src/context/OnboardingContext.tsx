import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const KEY = 'fgl:onboarding-complete';

interface OnboardingContextValue {
  /**
   * `null` until the persisted flag has been read from storage, then
   * `true`/`false`. RootNavigator treats `null` as "still loading" (shows
   * LoadingScreen) rather than defaulting to `false` — otherwise every
   * cold start would flash the intro tutorial for an instant before the
   * AsyncStorage read resolves, even for a user who already completed it.
   */
  onboardingComplete: boolean | null;
  /** Marks the tutorial as seen (Skip or the final "Get Started" both call this). Idempotent. */
  completeOnboarding: () => void;
}

const OnboardingContext = createContext<OnboardingContextValue | undefined>(undefined);

/**
 * First-launch intro tutorial gate — shaped like ShowcaseModeContext/
 * DensityContext: a single AsyncStorage-backed flag read once on mount.
 * Deliberately local-only (no /v1/preferences sync): whether *this
 * install* has shown the 5-slide carousel isn't a cross-device account
 * preference, it's per-device first-run state, same category as
 * ShowcaseModeContext's flag.
 *
 * Re-triggering the tutorial (More screen's "Replay intro tutorial") does
 * NOT go through this context at all — it just pushes the Onboarding
 * screen back onto the stack. This flag only decides what the *first*
 * screen after sign-in is.
 */
export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (cancelled) return;
        setOnboardingComplete(raw === '1');
      })
      .catch(() => {
        // Fail open — a broken read should never permanently trap a user
        // behind a tutorial gate that can't resolve.
        if (!cancelled) setOnboardingComplete(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const completeOnboarding = () => {
    setOnboardingComplete(true);
    AsyncStorage.setItem(KEY, '1').catch(() => {});
  };

  const value = useMemo<OnboardingContextValue>(
    () => ({ onboardingComplete, completeOnboarding }),
    [onboardingComplete],
  );

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
}

export function useOnboarding(): OnboardingContextValue {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within an OnboardingProvider');
  }
  return context;
}
