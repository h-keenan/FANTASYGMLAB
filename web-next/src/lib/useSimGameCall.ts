"use client";

import { useCallback, useEffect, useRef } from "react";

import { simGameErrorGate, simGameGate, type SimGameEnvelope, type SimGameGate } from "@/lib/simGame";

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
    try {
      const body = await fn();
      const gate = simGameGate(body);
      if (gate.kind === "ready") return body;
      if (gate.kind === "conflict") handlers.current.onConflict?.();
      handlers.current.onGate(gate);
      return null;
    } catch (error) {
      const gate = simGameErrorGate(error);
      if (gate) {
        if (gate.kind === "conflict") handlers.current.onConflict?.();
        handlers.current.onGate(gate);
        return null;
      }
      const message = error instanceof Error && error.message && !/^Request failed with status/.test(error.message)
        ? error.message
        : "Something went wrong. Try again.";
      handlers.current.onError(message);
      return null;
    }
  }, []);
}
