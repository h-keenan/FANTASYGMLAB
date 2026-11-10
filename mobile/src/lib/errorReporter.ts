import Constants from 'expo-constants';

import { createErrorReporter, type ErrorReporter, type SentryLike } from './errorReporterCore';

/**
 * Shared crash/error reporter. Sentry (@sentry/react-native) is initialised
 * ONLY when EXPO_PUBLIC_SENTRY_DSN is set at build time; otherwise errors are
 * logged on-device only (nothing is sent anywhere). The DSN is a public
 * identifier, but it is still supplied by env, never committed.
 */
let reporter: ErrorReporter | null = null;

function getReporter(): ErrorReporter {
  if (!reporter) {
    reporter = createErrorReporter({
      dsn: process.env.EXPO_PUBLIC_SENTRY_DSN,
      environment: __DEV__ ? 'development' : 'production',
      release: Constants.expoConfig?.version,
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      loadSentry: () => require('@sentry/react-native') as SentryLike,
      log: (message, error, context) => console.error(message, error, context ?? ''),
    });
  }
  return reporter;
}

/** Call once at startup. Also routes uncaught JS exceptions to the reporter when Sentry is off. */
export function initErrorReporter(): void {
  const r = getReporter();
  if (r.mode === 'sentry') return; // Sentry installs its own global handlers
  const errorUtils = (globalThis as { ErrorUtils?: {
    getGlobalHandler?: () => (e: unknown, isFatal?: boolean) => void;
    setGlobalHandler?: (h: (e: unknown, isFatal?: boolean) => void) => void;
  } }).ErrorUtils;
  const previous = errorUtils?.getGlobalHandler?.();
  errorUtils?.setGlobalHandler?.((error, isFatal) => {
    r.report(error, { isFatal: Boolean(isFatal), source: 'global_handler' });
    previous?.(error, isFatal);
  });
}

export function reportError(error: unknown, context?: Record<string, unknown>): void {
  getReporter().report(error, context);
}
