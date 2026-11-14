import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  SAMPLE_BANNER_BODY,
  SAMPLE_BANNER_TITLE,
  SAMPLE_CONNECT_BODY,
  SAMPLE_CONNECT_TITLE,
  SAMPLE_CTA_LABEL,
} from '../lib/sampleLeague';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Persistent "Sample league" label + connect CTA, shown above every tab of
 * the sample league. Web twin: web-next/src/components/SampleLeagueBanner.tsx.
 */
export default function SampleLeagueBanner({ onConnect }: { onConnect: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.wrap} accessibilityRole="summary" testID="sample-banner">
      <ToneBadge label={SAMPLE_BANNER_TITLE} color={colors.accent} />
      <AppText style={styles.body} numberOfLines={1}>
        {SAMPLE_BANNER_BODY}
      </AppText>
      <Button label={SAMPLE_CTA_LABEL} onPress={onConnect} size="sm" />
    </View>
  );
}

/** The closing module of a sample tab: what the real thing shows, with the one way to get it. Web twin: SampleConnectModule. */
export function SampleConnectModule({ onConnect }: { onConnect: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.module} testID="sample-connect-module">
      <AppText style={styles.moduleTitle}>{SAMPLE_CONNECT_TITLE}</AppText>
      <AppText style={styles.body}>{SAMPLE_CONNECT_BODY}</AppText>
      <Button label={SAMPLE_CTA_LABEL} onPress={onConnect} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  const card = {
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderLeftWidth: 3,
    borderLeftColor: colors.accent,
    backgroundColor: colors.surface,
  } as const;
  return StyleSheet.create({
    // One slim row: badge, short note, CTA.
    wrap: { ...card, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs, paddingHorizontal: spacing.md },
    module: { ...card, gap: spacing.sm, padding: spacing.md },
    moduleTitle: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    body: { flex: 1, fontSize: 13.5, color: colors.textSecondary, lineHeight: 18 },
  });
}
