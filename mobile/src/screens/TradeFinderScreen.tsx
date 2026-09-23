import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import ScreenHero from '../components/ScreenHero';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PlayerNameText from '../components/PlayerNameText';
import PositionBadge from '../components/PositionBadge';
import TradeValueHero from '../components/TradeValueHero';
import { api, type LineupPlayer, type TradeIdea } from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeFinder'>;

// Button height (paddingVertical * 2 + line height) plus its own gap above
// the orb clearance zone (see the `bottom` override on the button below) —
// the list's last row needs to clear both, not just the orb.
const SEARCH_BUTTON_CLEARANCE = 56 + spacing.sm + spacing.lg;

function RosterRow({
  player,
  selected,
  onToggle,
}: {
  player: LineupPlayer;
  selected: boolean;
  onToggle: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity style={[styles.rosterRow, selected && styles.rosterRowSelected]} onPress={onToggle}>
      <View style={[styles.checkbox, selected && styles.checkboxChecked]}>
        {selected ? <Ionicons name="checkmark" size={14} color="#fff" /> : null}
      </View>
      <PlayerAvatar playerId={player.player_id} size={36} tier={player.tier} style={styles.rosterAvatar} />
      <View style={styles.rosterTextGroup}>
        <PlayerNameText name={player.name ?? 'Unknown player'} style={styles.rosterName} />
        <View style={styles.rosterMetaRow}>
          <PositionBadge position={player.position} />
          <AppText style={styles.rosterMeta} numberOfLines={1}>
            {player.team ?? '—'}
          </AppText>
        </View>
      </View>
    </TouchableOpacity>
  );
}

function ResultCard({ idea }: { idea: TradeIdea }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <AnimatedCard style={styles.resultCard}>
      <View style={styles.resultHeaderRow}>
        <AppText style={styles.resultPartner} numberOfLines={1}>
          {idea.partner_team_name}
        </AppText>
        <TradeValueHero delta={idea.trade_gain} size="sm" />
      </View>
      <View style={styles.resultPackageRow}>
        <View style={styles.resultPackageSide}>
          <AppText style={styles.resultPackageLabel}>YOU SEND</AppText>
          {idea.package.send.map((asset, index) => (
            <AppText key={asset.player_id ?? `send-${index}`} style={styles.resultAssetName} numberOfLines={1}>
              {asset.name ?? asset.label ?? 'Unknown'}
            </AppText>
          ))}
        </View>
        <Ionicons name="swap-horizontal" size={16} color={colors.textTertiary} />
        <View style={styles.resultPackageSide}>
          <AppText style={styles.resultPackageLabel}>YOU RECEIVE</AppText>
          {idea.package.receive.map((asset, index) => (
            <AppText key={asset.player_id ?? `receive-${index}`} style={styles.resultAssetName} numberOfLines={1}>
              {asset.name ?? asset.label ?? 'Unknown'}
            </AppText>
          ))}
        </View>
      </View>
      <AppText style={styles.resultRationale} numberOfLines={4}>
        {idea.rationale}
      </AppText>
      <View style={styles.resultFooterRow}>
        <AppText style={styles.resultConfidence}>{idea.confidence_label} confidence</AppText>
        <AppText style={styles.resultRealism}>{idea.market_realism_label}</AppText>
      </View>
    </AnimatedCard>
  );
}

/**
 * "Select these specific players, find who'd want them" — coridian_'s own
 * trade-block request, distinct from Trade Hub's passive "here's what we'd
 * suggest" board. Reuses the exact same idea-generation engine and Trust
 * enforcement (GET /v1/leagues/{id}/trade-finder ->
 * modules.trade_hub_engine.generate_trade_finder_records), just restricted
 * to whatever the caller picks here instead of the unrestricted pool.
 */
export default function TradeFinderScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { strategy } = useGmStance(leagueId);
  const { lens } = useValuationLens(leagueId);

  const [roster, setRoster] = useState<LineupPlayer[]>([]);
  const [loadingRoster, setLoadingRoster] = useState(true);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);

  useScreenHeaderTitle(navigation, 'Trade Finder', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const result = await api.getLeagueMyTeam(leagueId, { lens });
          if (cancelled) return;
          if (result.reason) {
            setRosterError("Couldn't load your roster for this league.");
          } else {
            setRoster([...result.starters, ...result.bench]);
          }
        } catch (err) {
          if (!cancelled) setRosterError(err instanceof Error ? err.message : 'Failed to load your roster.');
        } finally {
          if (!cancelled) setLoadingRoster(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId, lens]),
  );

  const toggle = (playerId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(playerId)) next.delete(playerId);
      else next.add(playerId);
      return next;
    });
    setIdeas(null);
  };

  const search = async () => {
    setSearchError(null);
    setSearching(true);
    try {
      const result = await api.getTradeFinderIdeas(leagueId, Array.from(selectedIds), strategy, lens);
      setIdeas(result.ideas);
      if (result.ideas.length === 0 && result.reason) {
        setSearchError(
          result.reason === 'no_players_selected'
            ? 'Select at least one player to search with.'
            : "Couldn't search for trades right now.",
        );
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Could not search for trades.');
    } finally {
      setSearching(false);
    }
  };

  if (loadingRoster) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (rosterError) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{rosterError}</AppText>
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenHero title="TRADE FINDER" subtitle={leagueName} />
      <AppText style={styles.disclaimer}>
        Pick the players you'd actually consider moving — the engine searches every other roster in{' '}
        {leagueName} for plausible trades built around exactly that selection.
      </AppText>

      <FlatList
        data={roster}
        keyExtractor={(item) => item.player_id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance + SEARCH_BUTTON_CLEARANCE }]}
        ListHeaderComponent={
          ideas !== null ? (
            <View style={styles.resultsSection}>
              <AppText style={styles.sectionLabel}>
                {searching ? 'Searching…' : `${ideas.length} plausible trade${ideas.length === 1 ? '' : 's'} found`}
              </AppText>
              {searchError ? <AppText style={styles.error}>{searchError}</AppText> : null}
              {ideas.map((idea, index) => (
                <ResultCard key={`${idea.partner_team_name}-${index}`} idea={idea} />
              ))}
              <AppText style={styles.sectionLabel}>Your Roster</AppText>
            </View>
          ) : (
            <>
              {searchError ? <AppText style={styles.error}>{searchError}</AppText> : null}
              <AppText style={styles.sectionLabel}>Your Roster</AppText>
            </>
          )
        }
        ListEmptyComponent={
          <EmptyState icon="people-outline" title="No roster found" subtitle="Nothing to shop yet in this league." />
        }
        renderItem={({ item }) => (
          <RosterRow player={item} selected={selectedIds.has(item.player_id)} onToggle={() => toggle(item.player_id)} />
        )}
      />

      <TouchableOpacity
        style={[
          styles.searchButton,
          // Sits above GM Orb's own darkening scrim rather than inside it —
          // stacked there, the button's solid fill and the scrim gradient
          // read as one muddy double-treatment at the bottom of the screen.
          { bottom: orbClearance + spacing.sm },
          selectedIds.size === 0 && styles.searchButtonDisabled,
        ]}
        onPress={search}
        disabled={searching || selectedIds.size === 0}
      >
        {searching ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <AppText style={styles.searchButtonText}>
            Find Trades{selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}
          </AppText>
        )}
      </TouchableOpacity>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    container: { flex: 1, backgroundColor: colors.background },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.background,
      padding: spacing.xl,
    },
    disclaimer: {
      fontSize: 12,
      color: colors.textSecondary,
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.sm,
      lineHeight: 16,
    },
    listContent: { padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xl * 4, gap: spacing.sm },
    sectionLabel: {
      fontSize: 12,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      marginTop: spacing.md,
      marginBottom: spacing.sm,
    },
    rosterRow: {
      flexDirection: 'row',
      alignItems: 'center',
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      backgroundColor: colors.surface,
      marginBottom: spacing.xs,
    },
    rosterRowSelected: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    checkbox: {
      width: 22,
      height: 22,
      borderRadius: radii.sm,
      borderWidth: 1.5,
      borderColor: colors.borderStrong,
      alignItems: 'center',
      justifyContent: 'center',
      marginRight: spacing.sm,
    },
    checkboxChecked: { backgroundColor: colors.accent, borderColor: colors.accent },
    rosterAvatar: { marginRight: spacing.sm },
    rosterTextGroup: { flex: 1 },
    rosterName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
    rosterMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
    rosterMeta: { fontSize: 12, color: colors.textSecondary },
    resultsSection: { marginBottom: spacing.sm },
    resultCard: { padding: spacing.md, marginBottom: spacing.sm },
    resultHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
    resultPartner: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, flex: 1, marginRight: spacing.sm },
    resultPackageRow: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.sm,
      marginTop: spacing.sm,
    },
    resultPackageSide: { flex: 1, gap: 2 },
    resultPackageLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
    resultAssetName: { fontSize: 12, color: colors.textPrimary },
    resultRationale: { fontSize: 12, color: colors.textSecondary, lineHeight: 17, marginTop: spacing.sm },
    resultFooterRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      marginTop: spacing.sm,
      paddingTop: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
    resultConfidence: { fontSize: 11, color: colors.textSecondary, fontWeight: '600' },
    resultRealism: { fontSize: 11, color: colors.textTertiary },
    searchButton: {
      position: 'absolute',
      left: spacing.lg,
      right: spacing.lg,
      bottom: spacing.lg,
      backgroundColor: colors.accent,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      alignItems: 'center',
      ...({} as object),
    },
    searchButtonDisabled: { opacity: 0.4 },
    searchButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
  });
}
