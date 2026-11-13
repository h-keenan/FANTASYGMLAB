import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { simOpenKey, simParseOpen } from '../lib/simLayout';
import { spacing } from '../theme';

/**
 * The one collapsible card (mirrors web-next's Collapsible): a header
 * Pressable (accessibilityState.expanded) that toggles the body; the open
 * state is remembered per `id` in AsyncStorage. No animation, so reduced
 * motion needs no special casing.
 */
export default function Collapsible({
  id,
  title,
  summary,
  accent,
  defaultOpen = true,
  children,
  testID,
}: {
  /** Stable key for remembering the open state, e.g. "home.injuries". */
  id: string;
  title: ReactNode;
  /** Right-aligned, always visible (a count badge or one-line status). */
  summary?: ReactNode;
  accent?: string;
  defaultOpen?: boolean;
  children: ReactNode;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const [open, setOpen] = useState(defaultOpen);
  const [touched, setTouched] = useState(false);

  // Restore the remembered choice (unless the player already toggled this session).
  useEffect(() => {
    let cancelled = false;
    AsyncStorage.getItem(simOpenKey(id))
      .then((raw) => {
        if (!cancelled && !touched) setOpen(simParseOpen(raw, defaultOpen));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, defaultOpen]);

  const styles = useMemo(() => StyleSheet.create({ head: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 }, title: { flex: 1, minWidth: 0 }, chevron: { width: 14, textAlign: 'center', color: colors.textTertiary, fontSize: 14 } }), [colors]);

  function toggle() {
    const next = !open;
    setTouched(true);
    setOpen(next);
    AsyncStorage.setItem(simOpenKey(id), next ? '1' : '0').catch(() => {});
  }

  return (
    <AccentCard accent={accent ?? colors.accent} compact>
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={toggle} style={styles.head} testID={testID}>
        <View style={styles.title}>{typeof title === 'string' ? <AppText style={{ fontSize: 14, fontWeight: '800', textTransform: 'uppercase', color: colors.textPrimary }}>{title}</AppText> : title}</View>
        {summary ? <View>{summary}</View> : null}
        <AppText style={styles.chevron}>{open ? '−' : '+'}</AppText>
      </Pressable>
      {open ? <View style={{ gap: spacing.md }}>{children}</View> : null}
    </AccentCard>
  );
}
