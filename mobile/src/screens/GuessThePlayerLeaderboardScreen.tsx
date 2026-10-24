import React, { useCallback, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import BrandHeaderBar from '../components/BrandHeaderBar';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type GuessThePlayerLeaderboardEntry, type GuessThePlayerLeaderboardResponse } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GuessThePlayerLeaderboard'>;
type Mode = 'stat_line' | 'name_match';

const MODE_OPTIONS: Array<{ key: Mode; label: string }> = [
  { key: 'stat_line', label: 'Whose Stats' },
  { key: 'name_match', label: 'Who Is Who' },
];

/**
 * League-scoped Guess the Player leaderboard (port of web-next's
 * GuessThePlayerLeaderboardContent). "Leaguemates" are the other
 * FantasyDesk accounts that saved this same league, not every Sleeper
 * manager in it.
 */
export default function GuessThePlayerLeaderboardScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [data, setData] = useState<GuessThePlayerLeaderboardResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>('stat_line');
  const [tick, setTick] = useState(0);

  useScreenHeaderTitle(navigation, 'Leaderboard', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      api
        .getGuessThePlayerLeaderboard(leagueId)
        .then((result) => {
          if (cancelled) return;
          setData(result);
          setError(null);
        })
        .catch((err) => {
          if (!cancelled) setError(toUserErrorMessage(err, 'Could not load the leaderboard.'));
        });
      return () => {
        cancelled = true;
      };
    }, [leagueId, tick]),
  );

  if (!data && !error) return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  if (error || !data) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState
          title="Couldn't load the leaderboard"
          message={error}
          onRetry={() => {
            setError(null);
            setTick((n) => n + 1);
          }}
        />
      </View>
    );
  }

  const entries = data[mode].entries;

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.content, { paddingTop: headerHeight, paddingBottom: orbClearance }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <ScreenInfoNote
          label="How the leaderboard works"
          text="Real, persisted streaks among the other FantasyDesk users in this league, ranked by current streak, then best streak."
        />
        <SegmentedTabBar options={MODE_OPTIONS} active={mode} onChange={setMode} />
        <SectionHeading title="League Leaderboard" icon="trophy-outline" />
        {!data.configured ? (
          <EmptyState
            icon="cloud-offline-outline"
            title="Leaderboard unavailable"
            subtitle="The leaderboard isn't available right now. Check back later."
          />
        ) : entries.length === 0 ? (
          <EmptyState
            icon="people-outline"
            title="No leaguemates here yet"
            subtitle="Nobody else in this league has a FantasyDesk account yet. Invite your leaguemates to start a leaderboard."
            actionLabel="Invite leaguemates"
            onPressAction={() => navigation.navigate('More')}
          />
        ) : (
          <AnimatedCard style={styles.listCard}>
            {entries.map((entry, index) => (
              <LeaderboardRow
                key={entry.member_id}
                entry={entry}
                last={index === entries.length - 1}
                styles={styles}
                colors={colors}
              />
            ))}
          </AnimatedCard>
        )}
      </ScrollView>
    </View>
  );
}

function LeaderboardRow({
  entry,
  last,
  styles,
  colors,
}: {
  entry: GuessThePlayerLeaderboardEntry;
  last: boolean;
  styles: ReturnType<typeof createStyles>;
  colors: ThemeColors;
}) {
  return (
    <View style={[styles.row, entry.is_viewer && styles.rowMine, !last && styles.divider]}>
      <AppText style={[styles.rank, entry.rank === 1 && { color: colors.premium }]}>{entry.rank}</AppText>
      <View style={styles.nameWrap}>
        <AppText style={styles.name} numberOfLines={1}>
          {entry.display_name}
        </AppText>
        {entry.is_viewer ? <ToneBadge label="You" color={colors.success} size="xs" /> : null}
      </View>
      <View style={styles.right}>
        <AppText style={styles.streak}>
          {entry.current_streak} <AppText style={styles.muted}>streak</AppText>
        </AppText>
        <AppText style={styles.muted}>Best {entry.best_streak}</AppText>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    content: { padding: spacing.lg, gap: spacing.md },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, backgroundColor: colors.background },
    listCard: { paddingVertical: spacing.xs },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.md, minHeight: 56 },
    rowMine: { backgroundColor: colors.badgeBackground },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    rank: { width: 32, textAlign: 'center', fontSize: 15, fontWeight: '800', color: colors.textTertiary },
    nameWrap: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    name: { flexShrink: 1, fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    right: { alignItems: 'flex-end' },
    streak: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    muted: { fontSize: 12, fontWeight: '400', color: colors.textTertiary },
  });
}
