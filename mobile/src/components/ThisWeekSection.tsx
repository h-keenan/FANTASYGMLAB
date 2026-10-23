import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import SectionHeading from './SectionHeading';
import SkeletonBlock from './SkeletonBlock';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ThisWeek } from '../lib/api';
import { hasThisWeekContent, thisWeekTarget, thisWeekTitle, thisWeekToneKey } from '../lib/thisWeek';
import { spacing, type ThemeColors } from '../theme';

/**
 * The Dashboard's "This week" strip (mirrors web-next's ThisWeekStrip): up to
 * three moves with a one-line why each, or one next action outside the season.
 * Content comes from the server (modules/this_week.py).
 */
export default function ThisWeekSection({
  data,
  leagueId,
  leagueName,
  onNavigate,
  tradePending = false,
}: {
  data: ThisWeek | null | undefined;
  leagueId: string;
  leagueName: string;
  onNavigate: (name: string, params: object) => void;
  /** The progressive first Dashboard pass has no trade verdict yet: reserve
   * the trade row's space so the full response fills it without a layout jump. */
  tradePending?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!hasThisWeekContent(data)) return null;
  const go = (route: Parameters<typeof thisWeekTarget>[0]) => {
    const target = thisWeekTarget(route, leagueId, leagueName);
    onNavigate(target.name, target.params);
  };
  const next = data.next_action;
  return (
    <View style={styles.wrap}>
      <SectionHeading title={thisWeekTitle(data)} />
      {next ? (
        <AccentCard accent={colors.accent} compact>
          <AppText style={styles.headline}>{next.headline}</AppText>
          <AppText style={styles.why}>{next.why}</AppText>
          <Button label={next.cta_label} onPress={() => go(next.route)} style={styles.cta} />
        </AccentCard>
      ) : (
        data.rows.map((row) => {
          const color = colors[thisWeekToneKey(row.tone)];
          return (
            <AccentCard key={row.key} accent={color} compact>
              <View style={styles.titleRow}>
                <ToneBadge label={row.status} color={color} />
                <AppText style={[styles.headline, styles.flex]}>{row.headline}</AppText>
              </View>
              <AppText style={styles.why}>{row.why}</AppText>
              {row.cta_label && row.route ? (
                <Button label={row.cta_label} onPress={() => go(row.route!)} style={styles.cta} />
              ) : null}
            </AccentCard>
          );
        })
      )}
      {tradePending && !next && !data.rows.some((row) => row.key === 'trade') ? (
        <SkeletonBlock height={84} radius={12} />
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    flex: { flex: 1 },
    headline: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    why: { fontSize: 13, color: colors.textSecondary },
    cta: { alignSelf: 'flex-start', paddingVertical: spacing.sm },
  });
}
