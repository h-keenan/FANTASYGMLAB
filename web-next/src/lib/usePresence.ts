import { useEffect, useRef, useState } from "react";

import { presenceDurations, presenceMounted, presenceNext, presencePhaseMs, presenceSettle, type PresencePhase } from "./presence";
import { useReducedMotion } from "./useMotion";

export interface UsePresenceOptions {
  /** Enter / exit duration in ms, clamped to 120-300 (defaults 240 / 180). Both are 0 under reduced motion. */
  enterMs?: number;
  exitMs?: number;
  /** Animate in when it is already shown on the first render (default: it is simply there). */
  appear?: boolean;
  /** The exit finished and the content has just been unmounted. */
  onExited?: () => void;
}

export interface PresenceState {
  /** Render the content (shown, entering or still leaving). */
  mounted: boolean;
  phase: PresencePhase;
  enterMs: number;
  exitMs: number;
}

/**
 * THE appear / disappear hook (rules: lib/presence.ts). `show` flips: the content mounts and enters, or exits and then
 * unmounts after the exit duration. Reduced motion collapses both to 0, so it simply appears and disappears. The phase
 * is derived during render (no frame where a shown thing is missing); only the settle timer is an effect.
 */
export function usePresence(show: boolean, options: UsePresenceOptions = {}): PresenceState {
  const reduced = useReducedMotion();
  const d = presenceDurations(options, reduced);
  const [phase, setPhase] = useState<PresencePhase>(() => (show ? (options.appear ? presenceNext("exited", true, d) : "entered") : "exited"));
  const next = presenceNext(phase, show, d);
  if (next !== phase) setPhase(next);
  const current = next;

  const onExitedRef = useRef(options.onExited);
  useEffect(() => {
    onExitedRef.current = options.onExited;
  }, [options.onExited]);

  const previous = useRef<PresencePhase>(current);
  useEffect(() => {
    const before = previous.current;
    previous.current = current;
    if (current === "exited") {
      if (before !== "exited") onExitedRef.current?.();
      return;
    }
    const ms = presencePhaseMs(current, d);
    if (ms <= 0) return;
    const timer = setTimeout(() => setPhase((p) => presenceSettle(p)), ms);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, d.enterMs, d.exitMs]);

  return { mounted: presenceMounted(current), phase: current, enterMs: d.enterMs, exitMs: d.exitMs };
}
