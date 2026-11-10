import test from 'node:test';
import assert from 'node:assert/strict';
import { createErrorReporter, type SentryLike } from './errorReporterCore.ts';

function fakeSentry() {
  const calls: { init: Record<string, unknown>[]; captured: unknown[] } = { init: [], captured: [] };
  const sdk: SentryLike = {
    init: (o) => calls.init.push(o),
    captureException: (e) => calls.captured.push(e),
  };
  return { sdk, calls };
}

test('no DSN: never loads Sentry, logs locally', () => {
  const logs: string[] = [];
  let loaded = false;
  const r = createErrorReporter({
    dsn: '  ',
    loadSentry: () => { loaded = true; return fakeSentry().sdk; },
    log: (m) => logs.push(m),
  });
  r.report(new Error('x'));
  assert.equal(r.mode, 'log');
  assert.equal(loaded, false);
  assert.equal(logs.length, 1);
});

test('DSN set: initializes Sentry without PII/tracing and captures', () => {
  const { sdk, calls } = fakeSentry();
  const r = createErrorReporter({ dsn: 'https://k@o.ingest.sentry.io/1', loadSentry: () => sdk, log: () => {} });
  r.report(new Error('boom'));
  assert.equal(r.mode, 'sentry');
  assert.equal(calls.init[0].sendDefaultPii, false);
  assert.equal(calls.init[0].tracesSampleRate, 0);
  assert.equal(calls.captured.length, 1);
});

test('Sentry load failure degrades to log mode instead of crashing the app', () => {
  const logs: string[] = [];
  const r = createErrorReporter({ dsn: 'https://k@o/1', loadSentry: () => { throw new Error('no native module'); }, log: (m) => logs.push(m) });
  assert.equal(r.mode, 'log');
  r.report(new Error('x'));
  assert.equal(logs.length, 2);
});

test('a throwing sink never propagates', () => {
  const r = createErrorReporter({ dsn: '', loadSentry: () => fakeSentry().sdk, log: () => { throw new Error('sink'); } });
  assert.doesNotThrow(() => r.report(new Error('x')));
});
