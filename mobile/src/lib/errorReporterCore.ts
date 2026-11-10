/**
 * Pure core of the shared error reporter (no React Native imports so it runs
 * under `node --test`). Sentry is used ONLY when a DSN is configured; with no
 * DSN every report goes to the log sink (console), never off-device.
 */

export interface SentryLike {
  init: (options: Record<string, unknown>) => void;
  captureException: (error: unknown, hint?: Record<string, unknown>) => void;
}

export type ReporterMode = 'sentry' | 'log';

export interface ReporterOptions {
  dsn: string | undefined | null;
  environment?: string;
  release?: string;
  /** Lazily resolves the Sentry SDK; may throw if the native module is missing. */
  loadSentry: () => SentryLike;
  log: (message: string, error: unknown, context?: Record<string, unknown>) => void;
}

export interface ErrorReporter {
  mode: ReporterMode;
  report: (error: unknown, context?: Record<string, unknown>) => void;
}

export function createErrorReporter(opts: ReporterOptions): ErrorReporter {
  const dsn = (opts.dsn ?? '').trim();
  let sentry: SentryLike | null = null;
  if (dsn) {
    try {
      const sdk = opts.loadSentry();
      sdk.init({
        dsn,
        environment: opts.environment,
        release: opts.release,
        // Crash/error reporting only: no performance traces, no PII, no session replay.
        tracesSampleRate: 0,
        sendDefaultPii: false,
      });
      sentry = sdk;
    } catch (e) {
      opts.log('Sentry init failed; falling back to log-only error reporting', e);
    }
  }
  return {
    mode: sentry ? 'sentry' : 'log',
    report(error, context) {
      try {
        if (sentry) {
          sentry.captureException(error, context ? { extra: context } : undefined);
        } else {
          opts.log('Unhandled app error', error, context);
        }
      } catch {
        // Reporting must never throw into the error path it is reporting.
      }
    },
  };
}
