import { useCallback, useEffect, useRef } from 'react';

import type { SimGameEnvelope, SimGameGate } from './simGame';
import { runSimGameCall } from './simGameCall';

/** Hook form of runSimGameCall with stable identity; handlers can change freely. */
export function useSimGameRequest(onGate: (gate: SimGameGate) => void, onError: (message: string) => void, onConflict?: () => void) {
  const handlers = useRef({ onGate, onError, onConflict });
  useEffect(() => {
    handlers.current = { onGate, onError, onConflict };
  });
  return useCallback(
    <T extends SimGameEnvelope>(fn: () => Promise<T>): Promise<T | null> =>
      runSimGameCall(fn, {
        onGate: (gate) => handlers.current.onGate(gate),
        onError: (message) => handlers.current.onError(message),
        onConflict: () => handlers.current.onConflict?.(),
      }),
    [],
  );
}
