import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { SAMPLE_BANNER_BODY, SAMPLE_BANNER_TITLE, SAMPLE_CTA_LABEL } from '../lib/sampleLeague';
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
      <View style={styles.row}>
        <ToneBadge label={SAMPLE_BANNER_TITLE} color={colors.accent} />
        <AppText style={styles.body}>{SAMPLE_BANNER_BODY}</AppText>
      </View>
      <Button label={SAMPLE_CTA_LABEL} onPress={onConnect} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: {
      gap: spacing.sm,
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderLeftWidth: 3,
      borderLeftColor: colors.accent,
      backgroundColor: colors.surface,
    },
    row: { gap: spacing.sm, alignItems: 'flex-start' },
    body: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
  });
}
