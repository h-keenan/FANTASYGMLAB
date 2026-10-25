import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AppText from './AppText';
import SectionHeading from './SectionHeading';
import { SkeletonChart } from './SkeletonBlock';
import WeeklyPointsChart from './WeeklyPointsChart';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type WeeklyStatPoint } from '../lib/api';
import { radii, spacing, type ThemeColors } from '../theme';

// Mirrors services/mobile_api_service.py's MAX_WEEKLY_STATS_SEASONS_BACK —
// the weekly-stats endpoint serves up to 7 prior seasons on request. The
// year list is anchored on the season the endpoint itself reports as
// current (quick-view's `seasons` is always the current season only, so it
// can never build a picker).
const WEEKLY_STATS_SEASONS_BACK = 7;

/** "Rookie" or "N season(s)" -> prior seasons that could exist, so the year
 * picker doesn't offer years before the player was in the league. Null
 * (parse failure / no bio yet) falls back to the full window. */
function priorSeasonsFromExperience(yearsInLeague: string | null): number | null {
  if (!yearsInLeague) return null;
  if (yearsInLeague === 'Rookie') return 0;
  const match = /^(\d+)\s+season/.exec(yearsInLeague);
  return match ? Number(match[1]) : null;
}

/**
 * Points By Week with a season-back picker. The one implementation behind
 * Player Detail's Trends tab and the Player Quick View sheet (web twin:
 * PlayerTrendsPanel.tsx). Renders bare (no card) so each caller wraps it in
 * its own surface.
 */
export default function PlayerTrendsPanel({
  playerId,
  yearsInLeague,
}: {
  playerId: string;
  yearsInLeague: string | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Set once from the first response; the anchor for the year picker's
  // window, independent of whichever year the user has since tapped.
  const [defaultYear, setDefaultYear] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [weeks, setWeeks] = useState<WeeklyStatPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getPlayerWeeklyStats(playerId, selectedYear ?? undefined)
      .then((result) => {
        if (cancelled) return;
        setWeeks(result.weeks);
        setSelectedYear((current) => current ?? result.season);
        setDefaultYear((current) => current ?? result.season);
      })
      .catch(() => {
        if (!cancelled) setWeeks([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [playerId, selectedYear]);

  if (!loading && defaultYear === null) {
    return <AppText style={styles.notice}>No weekly trend data available for this player yet.</AppText>;
  }

  const priorSeasons = priorSeasonsFromExperience(yearsInLeague);
  const seasonCount =
    priorSeasons === null ? WEEKLY_STATS_SEASONS_BACK : Math.min(WEEKLY_STATS_SEASONS_BACK, priorSeasons + 1);
  const yearOptions = defaultYear === null ? [] : Array.from({ length: seasonCount }, (_, index) => defaultYear - index);

  return (
    <View>
      <SectionHeading title="Points By Week" icon="trending-up-outline" />
      {yearOptions.length > 1 ? (
        <View style={styles.yearRow}>
          {yearOptions.map((year) => (
            <TouchableOpacity
              key={year}
              style={[styles.yearPill, selectedYear === year && styles.yearPillActive]}
              onPress={() => setSelectedYear(year)}
              accessibilityRole="button"
              accessibilityLabel={`Season ${year}`}
            >
              <AppText style={[styles.yearPillText, selectedYear === year && styles.yearPillTextActive]}>{year}</AppText>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
      {loading || weeks === null ? <SkeletonChart /> : <WeeklyPointsChart weeks={weeks} />}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    // flexWrap: up to 7 season pills would overflow a narrow card otherwise.
    yearRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.md },
    yearPill: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radii.pill,
      backgroundColor: colors.surfaceSolid,
      borderWidth: 1,
      borderColor: colors.glassBorder,
    },
    yearPillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
    yearPillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    yearPillTextActive: { color: colors.onAccent },
    notice: { marginTop: spacing.md, fontSize: 12, color: colors.textSecondary, textAlign: 'center' },
  });
}
