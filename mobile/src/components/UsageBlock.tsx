import React, { useMemo } from 'react';
import { Linking, StyleSheet, View } from 'react-native';

import AnalyticsSection from './AnalyticsSection';
import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { UsageProfile } from '../lib/api';
import { formatUsageDelta, formatUsageValue, hasUsageContent, usageDataNote } from '../lib/usageProfile';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Usage block for the player detail Stats tab: rolling last-4 / last-8 usage
 * against the player's earlier games, role flags in plain English, and the
 * nflverse (CC BY 4.0) credit the data requires. Mobile twin of web-next's
 * PlayerUsageBlock.tsx; everything shown is decided server-side
 * (modules/usage_trends.py).
 */
export default function UsageBlock({ profile }: { profile: UsageProfile | null | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!hasUsageContent(profile)) return null;
  const showNote = profile.status === 'ok' || profile.status === 'building_sample' || profile.status === 'low_usage';
  const note = showNote ? usageDataNote(profile) : null;
  const directionColor = (direction: string) =>
    direction === 'up' ? colors.success : direction === 'down' ? colors.danger : colors.textTertiary;

  return (
    <AnalyticsSection title="Usage" icon="pulse-outline">
      {profile.status === 'unavailable' ? (
        <AppText style={styles.note}>Usage trends could not be calculated right now.</AppText>
      ) : null}
      {profile.flags.map((flag) => {
        const tint = flag.tone === 'positive' ? colors.success : colors.danger;
        return (
          <View key={flag.key} style={[styles.flag, { borderColor: tint }]}>
            <AppText style={[styles.flagLabel, { color: tint }]}>{flag.label.toUpperCase()}</AppText>
            <AppText style={styles.flagText}>{flag.explanation}</AppText>
          </View>
        );
      })}
      {profile.flags.length === 0 && profile.status_note ? (
        <AppText style={styles.note}>{profile.status_note}</AppText>
      ) : null}
      {profile.metrics.length > 0 ? (
        <View style={styles.table} accessibilityRole="summary">
          <View style={styles.row}>
            <AppText style={[styles.head, styles.labelCol]}>METRIC</AppText>
            <AppText style={[styles.head, styles.numCol]}>LAST 4</AppText>
            <AppText style={[styles.head, styles.numCol]}>LAST 8</AppText>
            <AppText style={[styles.head, styles.numCol]}>SEASON</AppText>
          </View>
          {profile.metrics.map((metric) => (
            <View key={metric.key} style={[styles.row, styles.rowBorder]}>
              <View style={styles.labelCol}>
                <AppText style={styles.metricLabel}>{metric.label}</AppText>
                {metric.delta_last4_vs_prior != null ? (
                  <AppText style={[styles.delta, { color: directionColor(metric.direction) }]}>
                    {formatUsageDelta(metric)} vs earlier
                  </AppText>
                ) : null}
              </View>
              <AppText style={[styles.value, styles.numCol]}>{formatUsageValue(metric, metric.last4)}</AppText>
              <AppText style={[styles.value, styles.numCol]}>{formatUsageValue(metric, metric.last8)}</AppText>
              <AppText style={[styles.value, styles.numCol]}>{formatUsageValue(metric, metric.season)}</AppText>
            </View>
          ))}
        </View>
      ) : null}
      {note ? <AppText style={styles.note}>{note}</AppText> : null}
      {profile.not_available?.length ? (
        <AppText style={styles.note}>
          Not shown: {profile.not_available.map((item) => item.label).join(', ')}. No free data source we can use in a
          paid app publishes it.
        </AppText>
      ) : null}
      {profile.attribution ? (
        <AppText
          style={styles.credit}
          accessibilityRole="link"
          onPress={() => void Linking.openURL(profile.attribution!.url)}
        >
          {profile.attribution.text}
        </AppText>
      ) : null}
    </AnalyticsSection>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    flag: {
      borderWidth: 1,
      borderRadius: radii.sm,
      padding: spacing.sm,
      marginBottom: spacing.sm,
      backgroundColor: colors.glass,
      gap: spacing.xs,
    },
    flagLabel: { fontSize: 11, fontWeight: '800', letterSpacing: 1 },
    flagText: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
    table: { borderWidth: StyleSheet.hairlineWidth * 1.5, borderColor: colors.glassBorder, borderRadius: radii.sm },
    row: { flexDirection: 'row', alignItems: 'baseline', paddingVertical: spacing.sm, paddingHorizontal: spacing.sm },
    rowBorder: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopColor: colors.glassBorder },
    labelCol: { flex: 1.9 },
    numCol: { flex: 0.8, textAlign: 'right' },
    head: { fontSize: 10, fontWeight: '600', letterSpacing: 0.8, color: colors.textTertiary },
    metricLabel: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
    delta: { fontSize: 11, fontWeight: '600' },
    value: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    note: { fontSize: 12, lineHeight: 17, color: colors.textTertiary, marginTop: spacing.sm },
    credit: { fontSize: 11, color: colors.textTertiary, textDecorationLine: 'underline', marginTop: spacing.sm },
  });
}
