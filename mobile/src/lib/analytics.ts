import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState, Platform } from 'react-native';

import { createAnalytics, parseAnalyticsFlag, type AnalyticsEvent } from './analyticsCore';
import { env } from './env';
import { supabase } from './supabase';

/**
 * Mobile product analytics -> the existing `POST /v1/analytics/event`
 * ingest (same pipeline and taxonomy as web-next/src/lib/analytics.ts).
 *
 * KILL SWITCH: ships DARK. Analytics is OFF unless the build sets
 * EXPO_PUBLIC_ANALYTICS_ENABLED=1 (see docs/analytics-coverage-2026-10.md).
 * Turning it on needs a new app build and, before that, the owner's sign-off
 * on the App Store "Data collection" answers.
 */

const REQUEST_TIMEOUT_MS = 8000;
const FLUSH_INTERVAL_MS = 30_000;

async function send(event: AnalyticsEvent): Promise<void> {
  let accessToken: string | undefined;
  try {
    const { data } = await supabase.auth.getSession();
    accessToken = data.session?.access_token;
  } catch {
    accessToken = undefined;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(`${env.apiBaseUrl}/v1/analytics/event`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ event: event.event, props: event.props, anon_id: event.anon_id }),
      signal: controller.signal,
    });
    // 5xx / 429 / transport errors keep the event queued; other 4xx would
    // never succeed. (429 used to be dropped as a "success".)
    if (response.status >= 500 || response.status === 429) throw new Error('server');
  } finally {
    clearTimeout(timer);
  }
}

const analytics = createAnalytics({
  enabled: () => parseAnalyticsFlag(process.env.EXPO_PUBLIC_ANALYTICS_ENABLED),
  send,
  storage: AsyncStorage,
  platform: Platform.OS,
});

export const trackEvent = analytics.track;
export const trackUse = analytics.trackUse;
export const trackScreen = analytics.trackScreen;
export const flushAnalytics = analytics.flush;
export const analyticsEnabled = analytics.isEnabled;

let started = false;

/** Call once at app start: app-open event, periodic flush, flush on background. */
export function startAnalytics(): () => void {
  if (started || !analytics.isEnabled()) return () => {};
  started = true;
  analytics.track('session_started', { source_surface: 'app_open' });
  const timer = setInterval(() => void analytics.flush(), FLUSH_INTERVAL_MS);
  const sub = AppState.addEventListener('change', (state) => {
    if (state === 'background' || state === 'inactive') void analytics.flush();
    if (state === 'active') analytics.track('session_started', { source_surface: 'app_foreground' });
  });
  void analytics.flush();
  return () => {
    clearInterval(timer);
    sub.remove();
    started = false;
  };
}
