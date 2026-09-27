import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const ANSWERED_KEY = 'fgl:college-football-prompt-answered';
const FOLLOWS_KEY = 'fgl:college-football-interest';

export type CollegeInterestStatus = 'loading' | 'unanswered' | 'yes' | 'no';

interface CollegeInterestContextValue {
  /**
   * `'loading'` until the persisted flags resolve, then one of:
   * `'unanswered'` (never answered or dismissed — show the one-time prompt),
   * `'yes'` (answered yes — surfaces the scouting/watchlist entry point),
   * `'no'` (answered no, OR dismissed without answering — both are a
   * permanent "don't ask again" with the entry point staying hidden; they
   * aren't distinguished because nothing downstream needs to tell them
   * apart, only `dismiss` vs `respond(false)` differ in which flags they
   * persist).
   */
  status: CollegeInterestStatus;
  /** User tapped Yes/No on the prompt. */
  respond: (follows: boolean) => void;
  /** User dismissed the prompt without answering — never ask again, but
   * don't unlock the scouting entry point either. */
  dismiss: () => void;
}

const CollegeInterestContext = createContext<CollegeInterestContextValue | undefined>(undefined);

/**
 * One-time, non-intrusive "Do you follow college football?" ask (coridian_:
 * "don't make it overbearing" — a single dismissible prompt, never a
 * blocking modal, never repeated once dismissed or answered). Shaped like
 * OnboardingContext: a local-only AsyncStorage flag, not synced
 * cross-device — whether *this install* has been asked is per-device
 * first-run state, not an account preference.
 *
 * Persistence: two independent flags rather than one enum string, so a
 * dismiss-without-answering and an explicit "no" answer are both
 * "never ask again" but stay distinguishable for analytics/debugging
 * without a migration if that distinction ever matters later.
 */
export function CollegeInterestProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<CollegeInterestStatus>('loading');

  useEffect(() => {
    let cancelled = false;
    Promise.all([AsyncStorage.getItem(ANSWERED_KEY), AsyncStorage.getItem(FOLLOWS_KEY)])
      .then(([answered, follows]) => {
        if (cancelled) return;
        if (answered !== '1') {
          setStatus('unanswered');
          return;
        }
        setStatus(follows === 'yes' ? 'yes' : 'no');
      })
      .catch(() => {
        // Fail open — never trap the prompt in a broken "loading" state.
        if (!cancelled) setStatus('unanswered');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const respond = (follows: boolean) => {
    setStatus(follows ? 'yes' : 'no');
    AsyncStorage.setItem(ANSWERED_KEY, '1').catch(() => {});
    AsyncStorage.setItem(FOLLOWS_KEY, follows ? 'yes' : 'no').catch(() => {});
  };

  const dismiss = () => {
    setStatus('no');
    AsyncStorage.setItem(ANSWERED_KEY, '1').catch(() => {});
  };

  const value = useMemo<CollegeInterestContextValue>(
    () => ({ status, respond, dismiss }),
    [status],
  );

  return <CollegeInterestContext.Provider value={value}>{children}</CollegeInterestContext.Provider>;
}

export function useCollegeInterest(): CollegeInterestContextValue {
  const context = useContext(CollegeInterestContext);
  if (!context) {
    throw new Error('useCollegeInterest must be used within a CollegeInterestProvider');
  }
  return context;
}
