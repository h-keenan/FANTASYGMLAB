import React, { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { UNDO_TOAST_MS } from '../lib/confirmInPlace';
import { radii, shadows, spacing, type ThemeColors } from '../theme';

/**
 * Twin of web-next's components/ui/UndoToast.tsx. The low-stakes alternative
 * to ConfirmInPlace: do the removal in the UI at once, show "Removed X. Undo"
 * for a few seconds, and only then commit it.
 */
export function UndoToast({ message, onUndo, onDone, durationMs = UNDO_TOAST_MS }: { message: string; onUndo: () => void; onDone: () => void; durationMs?: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const doneRef = useRef(onDone);
  useEffect(() => {
    doneRef.current = onDone;
  }, [onDone]);
  useEffect(() => {
    AccessibilityInfo.announceForAccessibility(`${message} Undo available.`);
    const timer = setTimeout(() => doneRef.current(), durationMs);
    return () => clearTimeout(timer);
  }, [durationMs, message]);
  return (
    <View style={[styles.wrap, { bottom: spacing.lg + insets.bottom + 56 }]} pointerEvents="box-none">
      <View style={styles.toast} accessibilityLiveRegion="polite">
        <AppText style={styles.text} numberOfLines={2}>
          {message}
        </AppText>
        <Pressable accessibilityRole="button" accessibilityLabel="Undo" onPress={onUndo} style={styles.undo} hitSlop={8}>
          <AppText style={styles.undoText}>Undo</AppText>
        </Pressable>
      </View>
    </View>
  );
}

/**
 * Deferred-commit removal (same contract as web). `schedule(item)` shows the
 * toast (call your own optimistic state update first) and, when it expires,
 * runs `commit(item)`. Undo calls `restore(item)` instead. A newer removal
 * commits the previous one right away; leaving the screen flushes it.
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
  useEffect(() => flush, [flush]);

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

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { position: 'absolute', left: spacing.lg, right: spacing.lg, alignItems: 'center' },
    toast: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      maxWidth: 420,
      paddingLeft: spacing.lg,
      paddingRight: spacing.sm,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.backgroundElevated,
      ...shadows.resting,
    },
    text: { flexShrink: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary, paddingVertical: spacing.sm },
    undo: { minHeight: 44, paddingHorizontal: spacing.md, alignItems: 'center', justifyContent: 'center' },
    undoText: { fontSize: 14, fontWeight: '800', color: colors.accent },
  });
}
