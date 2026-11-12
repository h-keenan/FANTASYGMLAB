/**
 * The one way a Fantasy Sim: the GM Game screen interprets an API call, pure so
 * it runs under node:test. Every body is classified by simGameGate
 * (premium_required is a normal 200 that did nothing; conflict and not-ready
 * reasons are messages, not crashes) and every thrown error by simGameErrorGate
 * (404 = flag off, 409 = raced write, 503 = busy). Returns the body only when
 * the call really succeeded, else null after reporting the gate, so callers
 * just `if (!body) return`. Mirrors web-next/src/lib/useSimGameCall.ts.
 */
import { simGameErrorGate, simGameGate, type SimGameEnvelope, type SimGameGate } from './simGame.ts';

export interface SimGameCallHandlers {
  onGate: (gate: SimGameGate) => void;
  onError: (message: string) => void;
  onConflict?: () => void;
}

export async function runSimGameCall<T extends SimGameEnvelope>(fn: () => Promise<T>, handlers: SimGameCallHandlers): Promise<T | null> {
  try {
    const body = await fn();
    const gate = simGameGate(body);
    if (gate.kind === 'ready') return body;
    if (gate.kind === 'conflict') handlers.onConflict?.();
    handlers.onGate(gate);
    return null;
  } catch (error) {
    const gate = simGameErrorGate(error);
    if (gate) {
      if (gate.kind === 'conflict') handlers.onConflict?.();
      handlers.onGate(gate);
      return null;
    }
    const message =
      error instanceof Error && error.message && !/^Request failed/.test(error.message)
        ? error.message
        : 'Something went wrong. Try again.';
    handlers.onError(message);
    return null;
  }
}
