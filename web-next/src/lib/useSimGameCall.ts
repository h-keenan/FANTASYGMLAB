"use client";

import { useCallback, useEffect, useRef } from "react";

import { simActionFailureMessage, simGameErrorGate, simGameGate, simIsTransientGate, type SimGameEnvelope, type SimGameGate } from "@/lib/simGame";

export const SIM_CALL_RETRY_MS = 700;

/**
 * The one way a game screen calls the API. Every body is classified by
 * simGameGate (premium_required is a normal 200 that did nothing; conflict and
 * not-ready reasons are messages, not crashes) and every thrown error by
 * simGameErrorGate (404 = flag off, 409 = raced write, 503 = busy). Returns
 * the body only when the call really succeeded, else null after reporting the
 * gate to `onGate`, so callers just `if (!body) return`.
 */
export function useSimGameCall(onGate: (gate: SimGameGate) => void, onError: (message: string) => void, onConflict?: () => void) {
  const handlers = useRef({ onGate, onError, onConflict });
  useEffect(() => {
    handlers.current = { onGate, onError, onConflict };
  });
  return useCallback(async function call<T extends SimGameEnvelope>(fn: () => Promise<T>): Promise<T | null> {
    // A storage hiccup or busy server on an ACTION retries once on its own, then reports
    // inline (the game stays on screen); only the initial load shows the full-page state.
    for (let attempt = 0; attempt < 2; attempt += 1) {
      let body: T | null = null;
      let gate: SimGameGate | null = null;
      try {
        body = await fn();
        gate = simGameGate(body);
        if (gate.kind === "ready") return body;
      } catch (error) {
        gate = simGameErrorGate(error);
        if (!gate) {
          const message = error instanceof Error && error.message && !/^Request failed with status/.test(error.message)
            ? error.message
            : "Something went wrong. Try again.";
          handlers.current.onError(message);
          return null;
        }
      }
      if (simIsTransientGate(gate)) {
        if (attempt === 0) {
          await new Promise((resolve) => setTimeout(resolve, SIM_CALL_RETRY_MS));
          continue;
        }
        handlers.current.onError(simActionFailureMessage(body, gate));
        return null;
      }
      if (gate.kind === "conflict") handlers.current.onConflict?.();
      handlers.current.onGate(gate);
      return null;
    }
    return null;
  }, []);
}
