import React, { useMemo } from 'react';
import { Linking, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PremiumLock from './PremiumLock';
import { StatRowsCard, type ExploreHandler } from './StatRows';
import { useThemeMode } from '../context/ThemeModeContext';
import type { UsageProfile } from '../lib/api';
import { poolCaption, usageRows } from '../lib/statRows';
import { hasUsageContent, usageDataNote } from '../lib/usageProfile';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Usage card for the quick view sheet and player detail: the role flag in plain
 * English, then the five usage numbers as the same percentile rows every other
 * stat uses (tap for the Percentile Explorer), each with its last-4 trend and
 * the nflverse (CC BY 4.0) credit. Mobile twin of web-next's PlayerUsageBlock;
 * everything shown is decided server-side (modules/usage_trends.py).
 */
export default function UsageBlock({
  profile,
  position,
  onExplore,
}: {
  profile: UsageProfile | null | undefined;
  position?: string | null;
  onExplore?: ExploreHandler;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!hasUsageContent(profile)) return null;
  const rows = usageRows(profile, position);
  const showNote = !profile.gated && (profile.status === 'ok' || profile.status === 'building_sample' || profile.status === 'low_usage');
  const note = showNote ? usageDataNote(profile) : null;
  const caption = rows.some((row) => row.percentile != null) ? poolCaption(position, profile.season) : null;
  return (
    <View>
      <StatRowsCard title="Usage" caption={caption ? `Percentile ${caption}` : null} rows={rows} onExplore={onExplore} collapseAfter={5}>
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
        {profile.flags.length === 0 && profile.status_note ? <AppText style={styles.note}>{profile.status_note}</AppText> : null}
      </StatRowsCard>
      {note ? <AppText style={styles.noteOut}>{note}</AppText> : null}
      {profile.gated && profile.gating ? (
        <PremiumLock
          feature="advanced_usage"
          title={profile.gating.upsell.title}
          description={`${profile.gating.upsell.body} Unlocks: ${profile.gating.unlocks.join('; ')}.`}
        />
      ) : null}
      {!profile.gated && profile.not_available?.length ? (
        <AppText style={styles.noteOut}>
          Not shown: {profile.not_available.map((item) => item.label).join(', ')}. No free data source we can use in a paid
          app publishes it.
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
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    flag: { borderWidth: 1, borderRadius: radii.sm, padding: spacing.sm, marginVertical: spacing.sm, gap: spacing.xs },
    flagLabel: { fontSize: 12.5, fontWeight: '800', letterSpacing: 1 },
    flagText: { fontSize: 14.5, lineHeight: 20, color: colors.textSecondary },
    note: { fontSize: 13.5, lineHeight: 19, color: colors.textTertiary, marginVertical: spacing.xs },
    noteOut: { fontSize: 12.5, lineHeight: 18, color: colors.textTertiary, marginBottom: spacing.xs },
    credit: { fontSize: 12.5, color: colors.textTertiary, textDecorationLine: 'underline', marginBottom: spacing.md },
  });
}
