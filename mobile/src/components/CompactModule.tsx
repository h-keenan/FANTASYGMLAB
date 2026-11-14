import AsyncStorage from '@react-native-async-storage/async-storage';
import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import { Sheet } from './Sheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { compactAriaLabel, compactParts, type CompactPart, type CompactTone } from '../lib/compactModule';
import { simOpenKey, simParseOpen } from '../lib/simLayout';
import { spacing, type ThemeColors } from '../theme';

function toneColor(tone: CompactTone | undefined, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'action': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return colors.textPrimary;
  }
}

/**
 * THE compact module (mirrors web-next/src/components/ui/CompactModule.tsx; docs/ui-patterns.md). Collapsed it is a
 * title plus a dense one-or-two-line summary of the key numbers and status (`parts`), with one optional trailing
 * `action` that works without expanding. Tap the header to expand inline (default) or into a shared Sheet
 * (`expandIn="sheet"`). The open state is remembered per `id` unless `persist` is false.
 */
export default function CompactModule({
  id,
  title,
  label,
  parts,
  summary,
  tone = 'accent',
  accent,
  action,
  defaultOpen = false,
  persist = true,
  expandIn = 'inline',
  children,
  testID,
}: {
  id: string;
  title: ReactNode;
  /** Plain-text name for screen readers and the sheet heading; defaults to `title` when it is a string. */
  label?: string;
  parts?: ReadonlyArray<CompactPart | null | undefined | false | ''>;
  /** Legacy right-aligned node (used when there are no `parts`). Prefer `parts`. */
  summary?: ReactNode;
  tone?: CompactTone;
  accent?: string;
  action?: ReactNode;
  defaultOpen?: boolean;
  persist?: boolean;
  expandIn?: 'inline' | 'sheet';
  children?: ReactNode;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  const [touched, setTouched] = useState(false);
  const shown = compactParts(parts ?? []);
  const name = label ?? (typeof title === 'string' ? title : 'Details');
  const hasBody = children != null && children !== false;

  useEffect(() => {
    if (!persist || expandIn === 'sheet') return;
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

  function toggle() {
    const next = !open;
    setTouched(true);
    setOpen(next);
    if (persist && expandIn === 'inline') AsyncStorage.setItem(simOpenKey(id), next ? '1' : '0').catch(() => {});
  }

  return (
    <AccentCard accent={accent ?? toneColor(tone, colors)} compact>
      <View style={styles.head}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={compactAriaLabel(name, shown, open)}
          accessibilityState={{ expanded: hasBody ? open : undefined, disabled: !hasBody }}
          onPress={hasBody ? toggle : undefined}
          style={styles.toggle}
          testID={testID}
        >
          <View style={styles.text}>
            <View style={styles.titleRow}>
              {typeof title === 'string' ? <AppText style={styles.title}>{title}</AppText> : title}
              {shown.length === 0 && summary ? <View style={styles.summary}>{summary}</View> : null}
            </View>
            {shown.length > 0 ? (
              <AppText style={styles.parts} numberOfLines={2} testID="compact-summary">
                {shown.map((part, i) => (
                  <AppText key={part.key} style={[styles.part, part.tone ? { color: toneColor(part.tone, colors) } : null, part.strong ? { fontWeight: '800' } : null]}>
                    {i > 0 ? <AppText style={styles.sep}>{' · '}</AppText> : null}
                    {part.text}
                  </AppText>
                ))}
              </AppText>
            ) : null}
          </View>
          {hasBody ? <AppText style={styles.chevron}>{open && expandIn === 'inline' ? '−' : '+'}</AppText> : null}
        </Pressable>
        {action ? <View style={styles.action}>{action}</View> : null}
      </View>
      {expandIn === 'inline' ? (
        open && hasBody ? <View style={{ gap: spacing.md }}>{children}</View> : null
      ) : (
        <Sheet open={open} onClose={() => setOpen(false)} title={name}>
          {children}
        </Sheet>
      )}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    head: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    toggle: { flex: 1, minWidth: 0, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    text: { flex: 1, minWidth: 0 },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    title: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.6, color: colors.textTertiary },
    summary: { flex: 1, minWidth: 0, alignItems: 'flex-end' },
    parts: { fontSize: 14, lineHeight: 19, color: colors.textPrimary },
    part: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
    sep: { color: colors.textTertiary, fontWeight: '400' },
    chevron: { width: 14, textAlign: 'center', color: colors.textTertiary, fontSize: 14 },
    action: { flexShrink: 0 },
  });
}
