import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import InsightRow from '../components/InsightRow';
import PortfolioSharePreviewModal from '../components/PortfolioSharePreviewModal';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type PortfolioFailedLeague, type PortfolioLeague, type PortfolioResponse } from '../lib/api';
import { categoryMeta } from '../lib/dashboardItemPresentation';
import { setLastLeague } from '../lib/lastLeague';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Navigation = NativeStackNavigationProp<RootStackParamList>;

function recordLabel(league: PortfolioLeague): string {
  if (league.wins == null && league.losses == null) return '';
  const base = `${league.wins ?? 0}-${league.losses ?? 0}`;
  return league.ties ? `${base}-${league.ties}` : base;
}

/**
 * coridian_-approved cross-league "Portfolio" view: standing/needs/
 * opportunities across every saved league at once, reusing GET /v1/portfolio
 * (services/mobile_api_service.py), which itself reuses the exact same
 * per-league engine the single-league Dashboard already uses
 * (modules.dashboard_engine.build_league_summary) — this screen adds no new
 * aggregation of its own, just a compact row per league.
 *
 * One continuous grouped surface with internal dividers (Magna Carta §12),
 * not a separately-bordered card per league: each row is a league identity +
 * record/rank header, plus that league's single highest-priority Next Move
 * tile rendered with the shared InsightRow (§28) — the same "top need or
 * opportunity" headline the Dashboard itself leads with, not a new summary.
 * Tapping a row jumps straight into that league's own Dashboard, the same
 * "switch and go manage it" behavior LeagueSwitcherHeaderButton already uses.
 */
export default function PortfolioScreen() {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const navigation = useNavigation<Navigation>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;

      async function load() {
        try {
          const result = await api.getPortfolio();
          if (!cancelled) setData(result);
        } catch (err) {
          if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load your portfolio.'));
        } finally {
          if (!cancelled) setLoading(false);
        }
      }

      setError(null);
      void load();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  const openLeague = useCallback(
    (league: PortfolioLeague) => {
      void setLastLeague({ leagueId: league.league_id, leagueName: league.league_name });
      navigation.navigate('Dashboard', { leagueId: league.league_id, leagueName: league.league_name });
    },
    [navigation],
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

  if (!data) return null;

  if (!data.is_premium) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <EmptyState
          icon="star-outline"
          title={data.upsell?.title ?? 'Portfolio is a Premium feature'}
          subtitle={
            data.upsell?.body ??
            'Upgrade to Premium to see your standing across every saved league in one place.'
          }
          actionLabel="Upgrade to Premium"
          onPressAction={() => navigation.navigate('Paywall')}
        />
      </View>
    );
  }

  if (data.leagues.length === 0 && data.failed_leagues.length === 0) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight }]}>
        <GridBackground />
        <EmptyState
          icon="layers-outline"
          title="No saved leagues yet"
          subtitle="Save a league from Home to see your standing, record, and top need or opportunity across every league here."
          actionLabel="Go to Home"
          onPressAction={() => navigation.navigate('Home')}
        />
      </View>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <FlatList
        style={styles.list}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        data={data.leagues}
        keyExtractor={(item) => item.league_id}
        ListHeaderComponent={
          <View style={styles.infoNoteWrap}>
            <View style={styles.infoNoteRow}>
              <ScreenInfoNote
                label="Portfolio"
                text="Your standing, record, and top need or opportunity across every saved league — tap a league to open its Dashboard."
              />
              {data.leagues.length > 0 ? (
                <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
                  <Ionicons name="share-outline" size={14} color={colors.textSecondary} />
                  <AppText style={styles.shareButtonText}>Share</AppText>
                </TouchableOpacity>
              ) : null}
            </View>
            {data.failed_leagues.length > 0 ? (
              <FailedLeaguesNote leagues={data.failed_leagues} colors={colors} styles={styles} />
            ) : null}
          </View>
        }
        renderItem={({ item, index }) => (
          <PortfolioLeagueCard
            league={item}
            isFirst={index === 0}
            isLast={index === data.leagues.length - 1}
            colors={colors}
            styles={styles}
            onPress={() => openLeague(item)}
          />
        )}
      />
      <PortfolioSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagues={data.leagues}
      />
    </View>
  );
}

function FailedLeaguesNote({
  leagues,
  colors,
  styles,
}: {
  leagues: PortfolioFailedLeague[];
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  const names = leagues.map((league) => league.league_name).join(', ');
  const plural = leagues.length === 1 ? 'league' : 'leagues';
  return (
    <View style={styles.failedNote}>
      <Ionicons name="alert-circle-outline" size={14} color={colors.textSecondary} style={styles.failedNoteIcon} />
      <AppText style={styles.failedNoteText}>
        {`Couldn't load ${leagues.length} ${plural} right now: ${names}. Everything else below is up to date.`}
      </AppText>
    </View>
  );
}

function PortfolioLeagueCard({
  league,
  isFirst,
  isLast,
  colors,
  styles,
  onPress,
}: {
  league: PortfolioLeague;
  isFirst: boolean;
  isLast: boolean;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  onPress: () => void;
}) {
  const isChampion = league.power_rank === 1;
  const rankColor = isChampion ? colors.premium : colors.accent;
  const record = recordLabel(league);
  const showHealthFlag = Boolean(league.health_flag) && league.health_flag !== 'Stable';
  const meta = league.top_item ? categoryMeta(colors)[league.top_item.category] ?? categoryMeta(colors).watch : null;

  return (
    <TouchableOpacity
      activeOpacity={0.7}
      onPress={onPress}
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
      ]}
    >
      <View style={styles.headerRow}>
        <View style={styles.identityGroup}>
          <AppText style={styles.teamName} numberOfLines={1}>
            {league.team_name || 'Unclaimed team'}
          </AppText>
          <AppText style={styles.leagueName} numberOfLines={1}>
            {league.league_name}
          </AppText>
          <View style={styles.metaRow}>
            {record ? <AppText style={styles.record}>{record}</AppText> : null}
            {showHealthFlag ? (
              <View style={styles.healthBadge}>
                <AppText style={styles.healthBadgeText} numberOfLines={1}>
                  {league.health_flag}
                </AppText>
              </View>
            ) : null}
          </View>
        </View>
        {league.power_rank != null ? (
          <View style={[styles.rankPill, isChampion && styles.rankPillFirst, { borderColor: `${rankColor}80` }]}>
            {isChampion ? (
              <Ionicons name="trophy" size={13} color={rankColor} style={styles.rankTrophy} />
            ) : (
              <AppText style={styles.rankLabel}>ROSTER POWER</AppText>
            )}
            <AppText style={[styles.rankValue, { color: rankColor }]}>
              {league.power_rank_tied ? `T-${league.power_rank}` : `#${league.power_rank}`}
            </AppText>
          </View>
        ) : null}
      </View>
      {league.top_item && meta ? (
        <InsightRow
          icon={meta.icon}
          color={meta.color}
          label={meta.label}
          headline={league.top_item.headline}
          detail={league.top_item.reason}
          last
        />
      ) : null}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    list: { backgroundColor: 'transparent' },
    listContent: { padding: spacing.lg },
    infoNoteWrap: { marginBottom: spacing.md, gap: spacing.sm },
    infoNoteRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    shareButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.cardBorder,
    },
    shareButtonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.xl,
      backgroundColor: colors.background,
    },
    error: { color: colors.danger, textAlign: 'center' },
    failedNote: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.xs,
      backgroundColor: colors.badgeBackground,
      borderRadius: radii.sm,
      padding: spacing.sm,
    },
    failedNoteIcon: { marginTop: 1 },
    failedNoteText: { flex: 1, fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    // Continuous grouped surface with internal dividers (Magna Carta §12) —
    // every saved league is a peer row in one portfolio, not N independently
    // bordered/shadowed cards.
    row: {
      backgroundColor: colors.surface,
      paddingHorizontal: spacing.md,
      paddingTop: spacing.md,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
    },
    rowFirst: { borderTopWidth: StyleSheet.hairlineWidth * 1.5, borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
    rowLast: { borderBottomWidth: StyleSheet.hairlineWidth * 1.5, borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md, paddingBottom: spacing.xs },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    headerRow: { flexDirection: 'row', alignItems: 'flex-start', paddingBottom: spacing.sm },
    identityGroup: { flex: 1, marginRight: spacing.sm },
    teamName: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    leagueName: { fontSize: 12, color: colors.textSecondary, marginTop: 1 },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
    record: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    healthBadge: {
      backgroundColor: `${colors.danger}1F`,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 1,
    },
    healthBadgeText: { fontSize: 10, fontWeight: '700', color: colors.danger },
    rankPill: {
      backgroundColor: colors.background,
      borderRadius: radii.sm,
      borderWidth: 1,
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      alignItems: 'center',
      minWidth: 52,
    },
    rankLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
    rankValue: { fontSize: 15, fontWeight: '700' },
    rankPillFirst: { backgroundColor: `${colors.premium}1F` },
    rankTrophy: { marginBottom: 1 },
  });
}
