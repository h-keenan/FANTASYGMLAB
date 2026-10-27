import { useEffect } from 'react';
import { AppState } from 'react-native';

import { useAuth } from '../context/AuthContext';
import { liveActivitiesEnabled, syncLiveActivity } from './liveActivity';

const POLL_MS = 60_000;

/** Mount once under AuthProvider. No-op (no timers, no listeners) while the feature flag is off. */
export function useLiveActivitySync(): void {
  const { session, isGuest } = useAuth();
  const signedIn = !!session;
  useEffect(() => {
    if (!liveActivitiesEnabled || !signedIn) return;
    void syncLiveActivity(isGuest);
    const timer = setInterval(() => {
      if (AppState.currentState === 'active') void syncLiveActivity(isGuest);
    }, POLL_MS);
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active') void syncLiveActivity(isGuest);
    });
    return () => {
      clearInterval(timer);
      sub.remove();
    };
  }, [signedIn, isGuest]);
}
