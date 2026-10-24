import { useEffect, useState } from "react";

/**
 * True once `active` has stayed true for `delayMs`; false again the instant
 * `active` goes false. Never a timed wait for content: the flag only gates
 * an extra "still loading" treatment (e.g. a branded splash) that disappears
 * the moment the real data arrives.
 */
export function useDelayedFlag(active: boolean, delayMs: number): boolean {
  const [elapsed, setElapsed] = useState(false);
  useEffect(() => {
    if (!active) return;
    const id = setTimeout(() => setElapsed(true), delayMs);
    return () => {
      clearTimeout(id);
      setElapsed(false);
    };
  }, [active, delayMs]);
  return active && elapsed;
}
