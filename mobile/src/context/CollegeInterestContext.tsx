import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

import { loadCollegeInterest, saveCollegeInterest } from '../lib/collegeInterestStore';
import { userStorage } from '../lib/userStorage';
import { useAuth } from './AuthContext';

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
 * blocking modal, never repeated once dismissed or answered). Personal
 * preference data, so it is scoped per user (lib/collegeInterestStore.ts,
 * account isolation audit): a second account on the phone is asked on its
 * own, and the first account's answer survives sign-out. Mounted inside
 * AuthProvider so it reloads when the signed-in user changes (AuthContext
 * applies the user to storage before it publishes the session).
 *
 * Persistence: two independent flags rather than one enum string, so a
 * dismiss-without-answering and an explicit "no" answer are both
 * "never ask again" but stay distinguishable for analytics/debugging
 * without a migration if that distinction ever matters later.
 */
export function CollegeInterestProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<CollegeInterestStatus>('loading');
  const { session } = useAuth();
  const userId = session?.user?.id ?? null;

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    if (!userId) return undefined;
    loadCollegeInterest(userStorage)
      .then((answer) => {
        if (!cancelled) setStatus(answer);
      })
      .catch(() => {
        // Fail open - never trap the prompt in a broken "loading" state.
        if (!cancelled) setStatus('unanswered');
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const respond = (follows: boolean) => {
    setStatus(follows ? 'yes' : 'no');
    saveCollegeInterest(userStorage, follows).catch(() => {});
  };

  const dismiss = () => {
    setStatus('no');
    saveCollegeInterest(userStorage, null).catch(() => {});
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
