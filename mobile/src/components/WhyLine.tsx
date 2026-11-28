import React, { useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PressableScale from './PressableScale';
import { Collapse } from './Presence';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * One short line with a "Why" toggle: the line is always visible, the longer reason opens under it on tap (compact,
 * tap-to-expand). Replaces a stacked explanatory paragraph. Twin of web-next/src/components/ui/WhyLine.tsx.
 */
export default function WhyLine({ line, children, label, testID }: { line: string; children: ReactNode; /** Plain-text name for the toggle's accessible label. */ label: string; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  return (
    <View testID={testID}>
      <View style={styles.row}>
        <AppText style={styles.line} numberOfLines={1}>
          {line}
        </AppText>
        <PressableScale
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`${label}. ${open ? 'Hide' : 'Show'} why`}
          onPress={() => setOpen((v) => !v)}
          style={styles.toggle}
          testID={testID ? `${testID}-toggle` : undefined}
        >
          <AppText style={styles.toggleText}>Why {open ? '⌃' : '⌄'}</AppText>
        </PressableScale>
      </View>
      <Collapse open={open}>
        <AppText style={styles.body}>{children}</AppText>
      </Collapse>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    line: { flex: 1, minWidth: 0, fontSize: 12.5, fontWeight: '600', color: colors.textSecondary },
    toggle: { minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.sm },
    toggleText: { fontSize: 12.5, fontWeight: '700', color: colors.accent },
    body: { fontSize: 12.5, color: colors.textTertiary, paddingBottom: spacing.xs },
  });
}
