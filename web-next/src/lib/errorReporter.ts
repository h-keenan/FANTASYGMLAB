/**
 * Browser error reporter. Sentry (@sentry/browser) is loaded lazily and ONLY
 * when NEXT_PUBLIC_SENTRY_DSN is set at build time; with no DSN nothing is
 * imported or sent and reports are a no-op beyond the existing first-party
 * `trackClientError` signal. No tracing, no replay, no default PII.
 */
type SentryModule = typeof import("@sentry/browser");

let sentryPromise: Promise<SentryModule | null> | null = null;

function dsn(): string {
  return (process.env.NEXT_PUBLIC_SENTRY_DSN ?? "").trim();
}

export function initErrorReporter(): Promise<SentryModule | null> {
  if (sentryPromise) return sentryPromise;
  const key = dsn();
  if (!key) {
    sentryPromise = Promise.resolve(null);
    return sentryPromise;
  }
  sentryPromise = import("@sentry/browser")
    .then((Sentry) => {
      Sentry.init({
        dsn: key,
        environment: process.env.NODE_ENV,
        tracesSampleRate: 0,
        sendDefaultPii: false,
      });
      return Sentry;
    })
    .catch(() => null);
  return sentryPromise;
}

/** Never throws. */
export function reportError(error: unknown, context?: Record<string, unknown>): void {
  void initErrorReporter()
    .then((Sentry) => {
      Sentry?.captureException(error, context ? { extra: context } : undefined);
    })
    .catch(() => undefined);
}

/** Test seam. */
export function resetErrorReporterForTests(): void {
  sentryPromise = null;
}
