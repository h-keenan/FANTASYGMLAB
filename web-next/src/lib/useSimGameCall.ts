"use client";

import { useCallback, useEffect, useRef } from "react";

import { SIM_DELTA_FRESH_MS, SIM_RECONCILE_MS, simActionFailureMessage, simApplyDelta, simGameErrorGate, simGameGate, simIsTransientGate, type SimGame, type SimGameDelta, type SimGameEnvelope, type SimGameGate } from "@/lib/simGame";

export const SIM_CALL_RETRY_MS = 700;

/**
 * The one way a game screen calls the API. Every body is classified by
 * simGameGate (premium_required is a normal 200 that did nothing; conflict and
 * not-ready reasons are messages, not crashes) and every thrown error by
 * simGameErrorGate (404 = flag off, 409 = raced write, 503 = busy). Returns
 * the body only when the call really succeeded, else null after reporting the
 * gate to `onGate`, so callers just `if (!body) return`. A successful action that carries a `delta`
 * (the header slice it changed) hands it to `onDelta` before returning, so the screen's header is current
 * without a second request.
 */
export function useSimGameCall(
  onGate: (gate: SimGameGate) => void,
  onError: (message: string) => void,
  onConflict?: () => void,
  onDelta?: (delta: SimGameDelta) => void,
) {
  const handlers = useRef({ onGate, onError, onConflict, onDelta });
  useEffect(() => {
    handlers.current = { onGate, onError, onConflict, onDelta };
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
        if (gate.kind === "ready") {
        if (body.delta) handlers.current.onDelta?.(body.delta);
        return body;
      }
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
      // A raced write (409) was rejected, nothing was saved: the server re-reads the newest game on the retry, so one silent retry applies
      // the tap instead of a "Try again" toast the player may never see (coridian_, 2026-11-14: "Take their counter ... turned back, and the
      // second tap worked"). A second conflict is reported as before.
      if (gate.kind === "conflict" && attempt === 0) {
        await new Promise((resolve) => setTimeout(resolve, 150));
        continue;
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

/**
 * A small action's own response carries the header slice it changed (`delta`): apply it, and right after one
 * answer `reloadGame()` with a background confirm instead of a second awaited request.
 */
export function useSimDeltaReload(fetchGame: () => Promise<void>, setGame: (fn: (g: SimGame | null) => SimGame | null) => void) {
  const state = useRef<{ at: number; timer: ReturnType<typeof setTimeout> | null }>({ at: 0, timer: null });
  useEffect(() => () => {
    if (state.current.timer) clearTimeout(state.current.timer);
  }, []);
  const onDelta = useCallback((delta: SimGameDelta) => {
    state.current.at = Date.now();
    setGame((g) => (g ? simApplyDelta(g, delta) : g));
  }, [setGame]);
  const reloadGame = useCallback(async () => {
    const s = state.current;
    if (Date.now() - s.at < SIM_DELTA_FRESH_MS) {
      if (s.timer) clearTimeout(s.timer);
      s.timer = setTimeout(() => void fetchGame(), SIM_RECONCILE_MS);
      return;
    }
    await fetchGame();
  }, [fetchGame]);
  return { onDelta, reloadGame };
}
