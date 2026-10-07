import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TeamAvatar from '../components/TeamAvatar';
import { api, type PlayoffOddsTeam } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { percentileColor } from '../lib/percentile';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'PlayoffOdds'>;

// Honest, not-ready-yet copy per real `reason` code from the backend (see
// modules.playoff_simulator.build_league_playoff_odds) — same convention
// GmPlanScreen/MatchupScreen use for their own `reason` fields.
const REASON_MESSAGES: Record<string, string> = {
  offseason: 'Playoff odds will be available once the regular season begins.',
  no_playoff_format: "This league's playoff format isn't set yet — odds need a real playoff-team count from league settings.",
  no_rankings_data: "We don't have enough roster data to compute Roster Power for this league yet.",
  unavailable: "Playoff odds aren't available for this league right now.",
};

export default function PlayoffOddsScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [teams, setTeams] = useState<PlayoffOddsTeam[]>([]);
  const [reason, setReason] = useState<string>('');
  const [weeksRemaining, setWeeksRemaining] = useState<number | null>(null);
  const [slopeFitted, setSlopeFitted] = useState(false);
  const [myRosterId, setMyRosterId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Playoff Odds', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const [oddsResult, myRosterResult] = await Promise.all([
            api.getLeaguePlayoffOdds(leagueId),
            api.getMyRoster(leagueId).catch(() => ({ ok: true as const, roster: null, reason: '' as const })),
          ]);
          if (cancelled) return;
          setTeams(oddsResult.teams ?? []);
          setReason(oddsResult.reason ?? '');
          setWeeksRemaining(oddsResult.weeks_remaining ?? null);
          setSlopeFitted(Boolean(oddsResult.slope_fitted));
          setMyRosterId(myRosterResult.roster ? String(myRosterResult.roster.roster_id ?? '') : '');
        } catch (err) {
          if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load playoff odds.'));
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      void load();
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
  );

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  if (reason || teams.length === 0) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <View style={styles.center}>
          <AppText style={styles.quietText}>
            {REASON_MESSAGES[reason] || 'Playoff odds are not available for this league right now.'}
          </AppText>
        </View>
      </View>
    );
  }

  const methodologyNote =
    weeksRemaining === 0
      ? 'The regular season is over (or your league has no games left to simulate), so these are today’s final results, not a projection.'
      : `Ranked by simulated playoff odds across thousands of simulated completions of the ${weeksRemaining ?? ''} remaining week${weeksRemaining === 1 ? '' : 's'}, using your league’s real schedule and Roster Power. ${
          slopeFitted
            ? 'Win probabilities are calibrated against this league’s own real results so far.'
            : 'Early in the season, so win probabilities use a standard default model until more real results come in.'
        } This is a probabilistic estimate, not a guarantee.`;

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <FlatList
        style={styles.list}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        data={teams}
        keyExtractor={(item) => String(item.roster_id)}
        ListHeaderComponent={
          <View style={styles.infoNoteWrap}>
            <ScreenInfoNote label="How Playoff Odds works" text={methodologyNote} />
          </View>
        }
        renderItem={({ item, index }) => (
          <PlayoffOddsRow
            item={item}
            isFirst={index === 0}
            isLast={index === teams.length - 1}
            isMine={Boolean(myRosterId) && String(item.roster_id) === myRosterId}
            colors={colors}
            styles={styles}
          />
        )}
      />
    </View>
  );
}

function PlayoffOddsRow({
  item,
  isFirst,
  isLast,
  isMine,
  colors,
  styles,
}: {
  item: PlayoffOddsTeam;
  isFirst: boolean;
  isLast: boolean;
  isMine: boolean;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const probabilityColor = percentileColor(item.playoff_probability, colors);
  const statusLabel = item.clinched ? 'Clinched' : item.eliminated ? 'Eliminated' : null;

  return (
    <View
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
        isMine && styles.rowMine,
      ]}
    >
      <TeamAvatar avatarId={item.avatar_url} size={36} style={styles.avatar} />
      <View style={styles.ownerGroup}>
        <View style={styles.nameRow}>
          <AppText style={styles.owner} numberOfLines={1}>
            {item.team_name}
          </AppText>
          {isMine ? (
            <View style={styles.mineBadge}>
              <AppText style={styles.mineBadgeText}>You</AppText>
            </View>
          ) : null}
        </View>
        <AppText style={styles.record}>
          {item.record_label ? `${item.record_label} · ` : ''}
          Proj. {item.median_final_wins}-{item.median_final_losses} · Seed #{item.median_seed}
        </AppText>
        {statusLabel ? (
          <View style={[styles.statusBadge, { backgroundColor: `${probabilityColor}1F` }]}>
            <AppText style={[styles.statusBadgeText, { color: probabilityColor }]}>{statusLabel}</AppText>
          </View>
        ) : null}
      </View>
      <View style={[styles.oddsPill, { borderColor: `${probabilityColor}80` }]}>
        <AppText style={styles.oddsLabel}>ODDS</AppText>
        <AppText style={[styles.oddsValue, { color: probabilityColor }]}>
          {Math.round(item.playoff_probability)}%
        </AppText>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    list: { backgroundColor: 'transparent' },
    listContent: { padding: spacing.lg },
    infoNoteWrap: { marginBottom: spacing.md },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.xl,
      backgroundColor: colors.background,
    },
    quietText: { color: colors.textSecondary, textAlign: 'center', fontSize: 15 },
    // Continuous grouped surface with internal dividers (Magna Carta §12),
    // same leaderboard shape TeamsScreen uses — every team is a peer row in
    // one ranked list, not N independent cards.
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.md,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
    },
    rowFirst: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
    rowLast: { borderBottomWidth: StyleSheet.hairlineWidth * 1.5, borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    rowMine: {
      borderLeftWidth: 3,
      borderLeftColor: colors.accent,
      backgroundColor: colors.badgeBackground,
    },
    avatar: { marginRight: spacing.sm },
    ownerGroup: { flex: 1, marginRight: spacing.sm },
    nameRow: { flexDirection: 'row', alignItems: 'center' },
    owner: { fontSize: 16, fontWeight: '500', color: colors.textPrimary, marginRight: spacing.sm, flexShrink: 1 },
    record: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    statusBadge: {
      alignSelf: 'flex-start',
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
      marginTop: spacing.xs,
    },
    statusBadgeText: { fontSize: 10, fontWeight: '700' },
    mineBadge: {
      backgroundColor: colors.accent,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 2,
    },
    mineBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },
    oddsPill: {
      backgroundColor: colors.background,
      borderRadius: radii.sm,
      borderWidth: 1,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      alignItems: 'center',
      minWidth: 56,
    },
    oddsLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
    oddsValue: { fontSize: 15, fontWeight: '700' },
    error: { color: colors.danger, textAlign: 'center' },
  });
}
