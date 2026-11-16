import React, { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AccessibilityInfo, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { ToastSlot } from './UndoToast';
import { useThemeMode } from '../context/ThemeModeContext';
import { NOTICE_MS, noticeText, noticeToneFor, type NoticeTone } from '../lib/notice';
import { radii, shadows, spacing, type ThemeColors } from '../theme';

/**
 * The one in-app notice for failures and confirmations (UI pass 5 D7): replaces the system `Alert.alert` popups
 * ("Could not update Watchlist", "Could not rename league", ...) that ignored the theme and needed a tap. It rises above the
 * bottom pill through the shared ToastSlot / Presence, announces itself to screen readers, and clears itself (errors last
 * longest). A newer notice replaces the current one. Decisions that need a button (delete account, confirms) stay dialogs.
 * `notify(message, tone)`, or `notify.alert(title, detail)` as the drop-in for the old two-argument alert.
 */
type Notify = ((message: string, tone?: NoticeTone) => void) & { alert: (title: string, detail?: string) => void };

const NoticeContext = createContext<Notify | null>(null);

export function NoticeProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<{ message: string; tone: NoticeTone; seq: number } | null>(null);
  const seq = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const notify = useMemo<Notify>(() => {
    const show = (message: string, tone: NoticeTone = 'info') => {
      seq.current += 1;
      if (timer.current) clearTimeout(timer.current);
      setNotice({ message, tone, seq: seq.current });
      AccessibilityInfo.announceForAccessibility(message);
      timer.current = setTimeout(() => setNotice(null), NOTICE_MS[tone]);
    };
    const fn = show as Notify;
    fn.alert = (title, detail) => show(noticeText(title, detail), noticeToneFor(title));
    return fn;
  }, []);

  return (
    <NoticeContext.Provider value={notify}>
      <View style={rootStyles.root}>
        {children}
        <ToastSlot show={notice !== null}>{notice ? <NoticeBody message={notice.message} tone={notice.tone} /> : null}</ToastSlot>
      </View>
    </NoticeContext.Provider>
  );
}

function NoticeBody({ message, tone }: { message: string; tone: NoticeTone }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const edge = tone === 'error' ? colors.danger : tone === 'success' ? colors.success : colors.glassBorder;
  return (
    <View style={[styles.toast, { borderColor: edge }]} accessibilityLiveRegion="polite" accessibilityRole="alert" testID="notice-toast">
      <AppText style={styles.text}>{message}</AppText>
    </View>
  );
}

const NOOP: Notify = Object.assign(() => {}, { alert: () => {} });

/** Falls back to a no-op outside the provider (tests, isolated stories) so a screen never throws for want of a toast. */
export function useNotice(): Notify {
  return useContext(NoticeContext) ?? NOOP;
}

const rootStyles = StyleSheet.create({ root: { flex: 1 } });

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    toast: {
      maxWidth: 420,
      paddingHorizontal: spacing.lg,
      paddingVertical: spacing.md,
      borderRadius: radii.pill,
      borderWidth: 1,
      backgroundColor: colors.backgroundElevated,
      ...shadows.resting,
    },
    text: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
  });
}
