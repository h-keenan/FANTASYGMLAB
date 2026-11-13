/**
 * The one way a Fantasy Sim: the GM Game screen interprets an API call, pure so
 * it runs under node:test. Every body is classified by simGameGate
 * (premium_required is a normal 200 that did nothing; conflict and not-ready
 * reasons are messages, not crashes) and every thrown error by simGameErrorGate
 * (404 = flag off, 409 = raced write, 503 = busy). Returns the body only when
 * the call really succeeded, else null after reporting the gate, so callers
 * just `if (!body) return`. Mirrors web-next/src/lib/useSimGameCall.ts.
 */
import { simActionFailureMessage, simGameErrorGate, simGameGate, simIsTransientGate, type SimGameEnvelope, type SimGameGate } from './simGame.ts';

export const SIM_CALL_RETRY_MS = 700;

export interface SimGameCallHandlers {
  onGate: (gate: SimGameGate) => void;
  onError: (message: string) => void;
  onConflict?: () => void;
  /** Test seam for the single automatic retry's delay. */
  retryMs?: number;
}

export async function runSimGameCall<T extends SimGameEnvelope>(fn: () => Promise<T>, handlers: SimGameCallHandlers): Promise<T | null> {
  // A storage hiccup or busy server on an ACTION retries once on its own, then reports
  // inline (the game stays on screen); only the initial load shows the full-page state.
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let body: T | null = null;
    let gate: SimGameGate | null = null;
    try {
      body = await fn();
      gate = simGameGate(body);
      if (gate.kind === 'ready') return body;
    } catch (error) {
      gate = simGameErrorGate(error);
      if (!gate) {
        const message =
          error instanceof Error && error.message && !/^Request failed/.test(error.message)
            ? error.message
            : 'Something went wrong. Try again.';
        handlers.onError(message);
        return null;
      }
    }
    if (simIsTransientGate(gate)) {
      if (attempt === 0) {
        await new Promise((resolve) => setTimeout(resolve, handlers.retryMs ?? SIM_CALL_RETRY_MS));
        continue;
      }
      handlers.onError(simActionFailureMessage(body));
      return null;
    }
    if (gate.kind === 'conflict') handlers.onConflict?.();
    handlers.onGate(gate);
    return null;
  }
  return null;
}
