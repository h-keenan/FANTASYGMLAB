import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';

const KEY = 'fgl:onboarding-complete';
// Armed when a genuine first run finishes; consumed once by HomeScreen right
// after the first league connects, which is where the Pro trial offer is now
// shown (it used to sit before connect). Persisted so an app kill between
// onboarding and connect does not silently drop the offer.
const TRIAL_OFFER_KEY = 'fgl:trial-offer-pending';

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
  /**
   * Same effect as `completeOnboarding`, but additionally arms a one-shot
   * "route into Team Situation after the first league is added" signal —
   * ONLY when this call is a genuine first run (`onboardingComplete` was
   * still `false` right before this call). A tutorial replay from
   * More > "Replay intro tutorial" always starts with `onboardingComplete`
   * already `true`, so calling this there never arms anything — it behaves
   * exactly like plain `completeOnboarding`. See OnboardingScreen's final
   * "Get Started" button and HomeScreen's `saveLeague` (Fix 1, welcome/
   * signup audit).
   */
  completeOnboardingViaGetStarted: () => void;
  /**
   * One-shot consume: true (and clears the signal) the first time this is
   * called after a genuine-first-run `completeOnboardingViaGetStarted`;
   * false otherwise (including every call after the first, or when Skip or
   * a replay completed onboarding instead).
   */
  consumeFirstLeagueTeamStanceRouting: () => boolean;
  /**
   * One-shot consume (async, persisted): true the first time it is called
   * after a genuine-first-run onboarding finished (Skip or Get Started);
   * false afterwards. HomeScreen calls it once the first league is saved and
   * then opens the Paywall as the trial offer.
   */
  consumeFirstLeagueTrialOffer: () => Promise<boolean>;
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
  // Ref, not state: purely an in-memory, single-use signal consumed within
  // the same app session (never persisted) — no screen needs a re-render
  // when this flips, only a later imperative read.
  const firstLeagueRoutingRef = useRef(false);

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
    // Only a genuine first run arms the trial offer (a replay observes true).
    if (onboardingComplete === false) AsyncStorage.setItem(TRIAL_OFFER_KEY, '1').catch(() => {});
    setOnboardingComplete(true);
    AsyncStorage.setItem(KEY, '1').catch(() => {});
  };

  const completeOnboardingViaGetStarted = () => {
    // Capture BEFORE completeOnboarding flips the flag: a genuine first run
    // is exactly the case where this read is still false. A replay always
    // observes `true` here already, so it's a no-op (matches
    // completeOnboarding's own existing idempotent-replay behavior).
    if (onboardingComplete === false) {
      firstLeagueRoutingRef.current = true;
    }
    completeOnboarding();
  };

  const consumeFirstLeagueTeamStanceRouting = () => {
    if (!firstLeagueRoutingRef.current) return false;
    firstLeagueRoutingRef.current = false;
    return true;
  };

  const consumeFirstLeagueTrialOffer = async () => {
    try {
      const raw = await AsyncStorage.getItem(TRIAL_OFFER_KEY);
      if (raw !== '1') return false;
      await AsyncStorage.removeItem(TRIAL_OFFER_KEY);
      return true;
    } catch {
      return false;
    }
  };

  const value = useMemo<OnboardingContextValue>(
    () => ({
      onboardingComplete,
      completeOnboarding,
      completeOnboardingViaGetStarted,
      consumeFirstLeagueTeamStanceRouting,
      consumeFirstLeagueTrialOffer,
    }),
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
