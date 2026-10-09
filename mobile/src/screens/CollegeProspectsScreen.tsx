import React, { useCallback, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import PositionBadge from '../components/PositionBadge';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ViewModeToggle from '../components/ViewModeToggle';
import { api, type CollegeProspect } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { usePlayerListViewMode } from '../lib/viewModePreference';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'CollegeProspects'>;
type FilterKey = 'all' | 'watchlist';

function aggregateLabel(prospect: CollegeProspect): string {
  const { avg_grade: avgGrade, scout_count: scoutCount } = prospect.aggregate;
  if (avgGrade == null || scoutCount === 0) return 'Not yet scouted';
  return `${avgGrade.toFixed(1)} avg · ${scoutCount} ${scoutCount === 1 ? 'scout' : 'scouts'}`;
}

/**
 * One prospect row — a bordered surface with hairline dividers per group
 * (Magna Carta §12), matching GmTargetsScreen's grouped-table treatment
 * rather than a per-row card. Trailing star toggles the personal watchlist
 * without leaving this screen; tapping the row itself opens
 * ProspectScoutingDetailScreen to submit/edit a grade.
 *
 * `grid`: coridian_'s 2-up compact card ask (Discord, 2026-10-09) — the
 * exact same fields (position, name, school/class, aggregate scout grade,
 * this user's own grade, watchlist star) reflowed into a vertical card.
 * This screen has no shared PlayerIdentityRow usage to extend (prospects
 * aren't rostered NFL players — no team/tier/injury/portrait, and
 * school/draft-class/scout-grade/watchlist are all genuinely page-specific
 * fields), so the grid variant lives locally here rather than forcing this
 * data into a generic player-row component.
 */
function ProspectRow({
  prospect,
  isFirst,
  isLast,
  grid = false,
  onPress,
  onToggleWatchlist,
}: {
  prospect: CollegeProspect;
  isFirst: boolean;
  isLast: boolean;
  grid?: boolean;
  onPress: () => void;
  onToggleWatchlist: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const starLabel = prospect.on_watchlist ? 'Remove from watchlist' : 'Add to watchlist';
  const starIcon = prospect.on_watchlist ? 'star' : 'star-outline';
  const starColor = prospect.on_watchlist ? colors.premium : colors.textSecondary;
  const classLabel = `${prospect.school}${prospect.draft_year ? ` · ${prospect.draft_year}` : ''}`;

  if (grid) {
    return (
      <TouchableOpacity style={styles.gridCell} onPress={onPress} activeOpacity={0.7}>
        <View style={styles.gridTopRow}>
          <PositionBadge position={prospect.position} />
          <TouchableOpacity
            style={styles.starButton}
            onPress={onToggleWatchlist}
            hitSlop={8}
            accessibilityLabel={starLabel}
          >
            <Ionicons name={starIcon} size={17} color={starColor} />
          </TouchableOpacity>
        </View>
        <AppText style={styles.gridName} numberOfLines={1}>
          {prospect.name}
        </AppText>
        <AppText style={styles.meta} numberOfLines={1}>
          {classLabel}
        </AppText>
        <View style={styles.gridTrailingFooter}>
          <AppText style={styles.aggregate} numberOfLines={1}>
            {aggregateLabel(prospect)}
          </AppText>
          {prospect.my_report ? (
            <AppText style={styles.myGrade} numberOfLines={1}>
              Your grade: {prospect.my_report.grade}/5
            </AppText>
          ) : null}
        </View>
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.row, isFirst && styles.rowFirst, isLast && styles.rowLast, !isLast && styles.rowDivider]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <PositionBadge position={prospect.position} />
      <View style={styles.identity}>
        <AppText style={styles.name} numberOfLines={1}>
          {prospect.name}
        </AppText>
        <AppText style={styles.meta} numberOfLines={1}>
          {classLabel}
        </AppText>
      </View>
      <View style={styles.trailing}>
        <AppText style={styles.aggregate} numberOfLines={1}>
          {aggregateLabel(prospect)}
        </AppText>
        {prospect.my_report ? (
          <AppText style={styles.myGrade}>Your grade: {prospect.my_report.grade}/5</AppText>
        ) : null}
      </View>
      <TouchableOpacity style={styles.starButton} onPress={onToggleWatchlist} hitSlop={8} accessibilityLabel={starLabel}>
        <Ionicons name={starIcon} size={18} color={starColor} />
      </TouchableOpacity>
    </TouchableOpacity>
  );
}

export default function CollegeProspectsScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [prospects, setProspects] = useState<CollegeProspect[]>([]);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { viewMode, setViewMode } = usePlayerListViewMode('college-prospects');

  useScreenHeaderTitle(navigation, 'College Prospects');

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.getCollegeProspects();
      setProspects(result.prospects);
    } catch (err) {
      setError(toUserErrorMessage(err, 'Failed to load prospects.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const toggleWatchlist = useCallback(async (prospect: CollegeProspect) => {
    const next = !prospect.on_watchlist;
    setProspects((prev) =>
      prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: next } : row)),
    );
    try {
      const result = next
        ? await api.addProspectToWatchlist(prospect.id)
        : await api.removeProspectFromWatchlist(prospect.id);
      if (!result.ok) {
        setProspects((prev) =>
          prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: !next } : row)),
        );
      }
    } catch {
      setProspects((prev) =>
        prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: !next } : row)),
      );
    }
  }, []);

  const visible = useMemo(
    () => (filter === 'watchlist' ? prospects.filter((p) => p.on_watchlist) : prospects),
    [prospects, filter],
  );

  const openDetail = useCallback(
    (prospect: CollegeProspect) => {
      navigation.navigate('CollegeProspectDetail', { prospect });
    },
    [navigation],
  );

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar />
      <ScreenInfoNote
        text="Every signed-in user's grade on a prospect pools into one shared signal — that shared aggregate, not any single grade, can influence rookie draft-class strength. Your own grade and watchlist stay yours to edit any time."
      />

      <View style={styles.tabRow}>
        <SegmentedTabBar
          options={[
            { key: 'all', label: 'All Prospects' },
            { key: 'watchlist', label: 'My Watchlist' },
          ]}
          active={filter}
          onChange={setFilter}
        />
        <ViewModeToggle value={viewMode} onChange={setViewMode} />
      </View>

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        key={viewMode}
        data={visible}
        keyExtractor={(item) => item.id}
        numColumns={viewMode === 'grid' ? 2 : 1}
        columnWrapperStyle={viewMode === 'grid' ? styles.gridRow : undefined}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        ListEmptyComponent={
          <EmptyState
            icon={filter === 'watchlist' ? 'star-outline' : 'school-outline'}
            title={filter === 'watchlist' ? 'No prospects followed yet' : 'No prospects yet'}
            subtitle={
              filter === 'watchlist'
                ? 'Tap the star on any prospect to follow them here.'
                : 'Check back soon — the prospect pool is still growing.'
            }
          />
        }
        renderItem={({ item, index }) => (
          <ProspectRow
            prospect={item}
            isFirst={index === 0}
            isLast={index === visible.length - 1}
            grid={viewMode === 'grid'}
            onPress={() => openDetail(item)}
            onToggleWatchlist={() => void toggleWatchlist(item)}
          />
        )}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
    tabRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.sm,
      gap: spacing.sm,
    },
    listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      backgroundColor: colors.surface,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
    },
    rowFirst: {
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopLeftRadius: radii.md,
      borderTopRightRadius: radii.md,
    },
    rowLast: {
      borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
      borderBottomLeftRadius: radii.md,
      borderBottomRightRadius: radii.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    identity: { flex: 1, minWidth: 0 },
    name: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
    trailing: { alignItems: 'flex-end', gap: 1 },
    aggregate: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
    myGrade: { fontSize: 10, color: colors.accent, marginTop: 1 },
    starButton: { padding: spacing.xs },
    // Grid (2-up compact card) mode — see ProspectRow's `grid` branch. Same
    // width/space-between approach as the other grid-ified list screens
    // (keeps an unpaired last card from stretching to double width).
    gridRow: { justifyContent: 'space-between', marginBottom: spacing.sm },
    gridCell: {
      width: '48%',
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.sm,
      gap: 2,
    },
    gridTopRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
    gridName: { fontSize: 13, fontWeight: '700', color: colors.textPrimary, marginTop: 2 },
    gridTrailingFooter: {
      marginTop: spacing.xs,
      paddingTop: spacing.xs,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
      gap: 1,
    },
    error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
