"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { UNDO_TOAST_MS } from "@/lib/confirmInPlace";

import "./ui.css";

/**
 * The low-stakes alternative to ConfirmInPlace: do the removal in the UI at
 * once, show "Removed X. Undo" for a few seconds, and only then commit it.
 * Use for things that are trivial to put back (a GM target, a trade asset).
 */
export function UndoToast({ message, onUndo, onDone, durationMs = UNDO_TOAST_MS }: { message: string; onUndo: () => void; onDone: () => void; durationMs?: number }) {
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);
  useEffect(() => {
    const timer = window.setTimeout(() => doneRef.current(), durationMs);
    return () => window.clearTimeout(timer);
  }, [durationMs]);
  return (
    <div className="ui-toast" role="status" aria-live="polite">
      <span className="ui-toast-text">{message}</span>
      <button type="button" className="ui-toast-undo" onClick={onUndo}>
        Undo
      </button>
    </div>
  );
}

/**
 * Deferred-commit removal. `schedule(item)` hides it (call your own
 * optimistic state update first), shows the toast and, when the toast
 * expires, runs `commit(item)`. Undo calls `restore(item)` instead. A newer
 * removal commits the previous one right away; leaving the page flushes it,
 * so an undo window never loses a removal.
 */
export function useUndoableRemoval<T>({
  message,
  commit,
  restore,
  durationMs = UNDO_TOAST_MS,
}: {
  message: (item: T) => string;
  commit: (item: T) => void | Promise<void>;
  restore: (item: T) => void;
  durationMs?: number;
}): { schedule: (item: T) => void; toast: ReactNode } {
  const [pending, setPending] = useState<{ item: T; seq: number } | null>(null);
  const seqRef = useRef(0);
  const pendingRef = useRef<T | null>(null);
  const commitRef = useRef(commit);
  useEffect(() => {
    commitRef.current = commit;
  }, [commit]);

  const flush = useCallback(() => {
    const item = pendingRef.current;
    pendingRef.current = null;
    if (item !== null) void commitRef.current(item);
  }, []);

  useEffect(() => flush, [flush]); // leaving the page commits

  const schedule = useCallback(
    (item: T) => {
      flush();
      pendingRef.current = item;
      seqRef.current += 1;
      setPending({ item, seq: seqRef.current });
    },
    [flush],
  );

  const toast =
    pending !== null ? (
      <UndoToast
        key={pending.seq}
        message={message(pending.item)}
        durationMs={durationMs}
        onUndo={() => {
          const item = pendingRef.current;
          pendingRef.current = null;
          setPending(null);
          if (item !== null) restore(item);
        }}
        onDone={() => {
          flush();
          setPending(null);
        }}
      />
    ) : null;

  return { schedule, toast };
}
