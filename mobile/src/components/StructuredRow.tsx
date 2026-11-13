import React, { useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { Sheet } from './Sheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { seeAllLabel, visibleSignalRows } from '../lib/draftSignals';
import { radii, spacing, type ThemeColors } from '../theme';

export type StructuredRowPill = { key: string; label: string };

export type StructuredRowProps = {
  /** Crest or avatar. Keep it a fixed 36pt box so every row lines up. */
  lead?: ReactNode;
  /** One line, truncated. */
  title: string;
  /** Status chip: label + colour. */
  chip?: { label: string; color: string } | null;
  /** Two or three metric pills at most. */
  pills?: readonly StructuredRowPill[];
  /** One short line (60 characters at most). The long sentence belongs in `detail`. */
  reason?: string;
  /** Gold outline: the signed-in user's own row. */
  highlight?: boolean;
  /** What a screen reader hears for the row button. */
  spoken?: string;
  detailTitle?: string;
  /** Sheet body. Without `detail` and `onOpen` the row is not tappable and shows no chevron. */
  detail?: ReactNode;
  onOpen?: () => void;
  testID?: string;
};

/**
 * Twin of web-next's components/ui/StructuredRow.tsx: crest + name + status
 * chip + metric pills + one short reason + chevron; tap opens a detail Sheet.
 * The replacement for delimiter-joined strings and generated sentences.
 */
export default function StructuredRow({ lead, title, chip, pills = [], reason, highlight = false, spoken, detailTitle, detail, onOpen, testID }: StructuredRowProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const tappable = Boolean(detail || onOpen);

  const body = (
    <>
      {lead ? <View style={styles.lead}>{lead}</View> : null}
      <View style={styles.main}>
        <View style={styles.line}>
          <AppText style={styles.title} numberOfLines={1}>
            {title}
          </AppText>
          {pills.length ? (
            <View style={styles.pills}>
              {pills.map((pill) => (
                <View key={pill.key} style={styles.pill}>
                  <AppText style={styles.pillText}>{pill.label}</AppText>
                </View>
              ))}
            </View>
          ) : null}
        </View>
        {chip || reason ? (
          <View style={styles.line}>
            {chip ? (
              <View style={[styles.chip, { borderColor: chip.color }]}>
                <AppText style={[styles.chipText, { color: chip.color }]}>{chip.label}</AppText>
              </View>
            ) : null}
            {reason ? (
              <AppText style={styles.reason} numberOfLines={1}>
                {reason}
              </AppText>
            ) : null}
          </View>
        ) : null}
      </View>
      {tappable ? <AppText style={styles.chevron}>›</AppText> : null}
    </>
  );

  return (
    <>
      {tappable ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={spoken ?? title}
          accessibilityHint={detail ? 'Opens details' : undefined}
          onPress={() => (onOpen ? onOpen() : setOpen(true))}
          style={({ pressed }) => [styles.row, highlight && styles.me, pressed && styles.pressed]}
          testID={testID}
        >
          {body}
        </Pressable>
      ) : (
        <View style={[styles.row, highlight && styles.me]} testID={testID}>
          {body}
        </View>
      )}
      {detail ? (
        <Sheet open={open} onClose={() => setOpen(false)} title={detailTitle ?? title} size="sm">
          {detail}
        </Sheet>
      ) : null}
    </>
  );
}

/** The first few rows, then "See all (n)" which expands the rest in place. */
export function StructuredRowList<T>({
  items,
  renderRow,
  top,
}: {
  items: readonly T[];
  renderRow: (item: T, index: number) => ReactNode;
  /** Rows shown before "See all". Default 3. */
  top?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [expanded, setExpanded] = useState(false);
  if (items.length === 0) return null;
  const shown = visibleSignalRows(items, expanded, top);
  const more = seeAllLabel(items.length, top);
  return (
    <View style={styles.list}>
      {shown.map((item, index) => (
        <View key={index}>{renderRow(item, index)}</View>
      ))}
      {more ? (
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ expanded }}
          onPress={() => setExpanded((value) => !value)}
          style={styles.more}
        >
          <AppText style={styles.moreText}>{expanded ? 'Show less' : more}</AppText>
        </Pressable>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    list: { gap: spacing.xs },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      minHeight: 52,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
    },
    me: { borderColor: colors.premium },
    pressed: { opacity: 0.8 },
    lead: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
    main: { flex: 1, minWidth: 0, gap: 3 },
    line: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    title: { flex: 1, minWidth: 0, fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    pills: { flexDirection: 'row', gap: 4 },
    pill: { paddingHorizontal: 7, paddingVertical: 1, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.border },
    pillText: { fontSize: 12, fontWeight: '800', color: colors.textSecondary },
    chip: { paddingHorizontal: 7, paddingVertical: 0, borderRadius: radii.pill, borderWidth: 1 },
    chipText: { fontSize: 12, fontWeight: '800' },
    reason: { flex: 1, minWidth: 0, fontSize: 13, color: colors.textTertiary },
    chevron: { fontSize: 22, color: colors.textTertiary },
    more: { alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.sm },
    moreText: { fontSize: 14, fontWeight: '800', color: colors.accent },
  });
}
