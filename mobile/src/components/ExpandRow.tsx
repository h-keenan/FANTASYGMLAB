import React, { useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { Collapse } from './Presence';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * THE one-line expandable row (twin of web-next/src/components/ui/ExpandRow.tsx): a leading mark (usually a player
 * avatar), ONE short line, an optional trailing action and a chevron. Tapping the line opens `children` (the full reason /
 * detail) under it; the action works without opening. Rows sit in an `ExpandRowGroup` (one grouped surface with dividers,
 * never a card per row). Used by Today's "Do this now" and More.
 */
export function ExpandRow({
  leading,
  title,
  caption,
  chips,
  action,
  children,
  testID,
  label,
  defaultOpen = false,
}: {
  leading?: ReactNode;
  title: string;
  /** A short line (string) or a node (Today's add -> drop pair). */
  caption?: ReactNode;
  /** Optional wrapping chip strip (status pills) under the line. */
  chips?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  testID?: string;
  label: string;
  defaultOpen?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  const hasBody = children != null && children !== false;
  const line = (
    <>
      {leading}
      <View style={styles.text}>
        <AppText style={styles.title}>{title}</AppText>
        {caption ? (typeof caption === 'string' ? <AppText style={styles.caption}>{caption}</AppText> : caption) : null}
        {chips ? <View style={styles.chips}>{chips}</View> : null}
      </View>
    </>
  );
  return (
    <View testID={testID}>
      <View style={styles.row}>
        {hasBody ? (
          <PressableScale accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={`${label}. ${open ? 'Hide' : 'Show'} details`} onPress={() => setOpen((v) => !v)} style={styles.toggle} testID={testID ? `${testID}-toggle` : undefined}>
            {line}
            <AppText style={styles.chevron}>{open ? '⌃' : '⌄'}</AppText>
          </PressableScale>
        ) : (
          <View style={styles.toggle}>{line}</View>
        )}
        {action}
      </View>
      {hasBody ? (
        <Collapse open={open}>
          <View style={styles.body}>{children}</View>
        </Collapse>
      ) : null}
    </View>
  );
}

/** The grouped surface for a stack of ExpandRows: one card, hairline dividers between rows. */
export function ExpandRowGroup({ accent, children, testID }: { accent: string; children: ReactNode; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const rows = React.Children.toArray(children);
  return (
    <View style={[styles.group, { borderLeftColor: accent }]} testID={testID}>
      {rows.map((row, i) => (
        <View key={i} style={i > 0 ? styles.divider : null}>
          {row}
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    group: { borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 3, backgroundColor: colors.surface, paddingHorizontal: spacing.md },
    divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 48 },
    toggle: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 48 },
    text: { flex: 1, minWidth: 0 },
    title: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginTop: 4 },
    caption: { fontSize: 12.5, color: colors.textTertiary },
    chevron: { fontSize: 14, color: colors.textTertiary },
    body: { gap: spacing.sm, paddingBottom: spacing.sm, paddingTop: spacing.xs },
  });
}

export default ExpandRow;
