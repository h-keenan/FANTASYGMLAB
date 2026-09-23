import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PremiumLock from '../components/PremiumLock';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TierBadge from '../components/TierBadge';
import { api, type WaiverPlayer, type WaiverPriorityAdd } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Waivers'>;

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE'];
const BEST_AVAILABLE_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K'];

const INJURY_RISK_STATUSES = new Set(['out', 'ir', 'doubtful', 'pup', 'suspended']);
const INJURY_WATCH_STATUSES = new Set(['questionable', 'sus']);

function injuryPillColor(status: string | null, colors: ThemeColors): string | null {
  const normalized = (status ?? '').trim().toLowerCase();
  if (!normalized) return null;
  if (INJURY_RISK_STATUSES.has(normalized)) return colors.danger;
  if (INJURY_WATCH_STATUSES.has(normalized)) return colors.premium;
  return null;
}

function opponentLabel(player: Pick<WaiverPlayer, 'opponent' | 'opponent_is_home'>): string | null {
  if (!player.opponent) return null;
  return `${player.opponent_is_home ? 'vs' : '@'} ${player.opponent}`;
}

const NO_LEAGUE_REASONS = new Set([
  'no_sleeper_username_linked',
  'sleeper_user_not_found',
  'not_a_member_of_league',
]);

function reasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see waivers.";
  }
  if (reason === 'empty_roster') {
    return "Your roster in this league looks empty, so there's nothing to weigh adds against yet.";
  }
  if (reason === 'no_player_data') {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}

export default function WaiversScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const { lens } = useValuationLens(leagueId);
  const [freeAgents, setFreeAgents] = useState<WaiverPlayer[] | null>(null);
  const [priorityAdds, setPriorityAdds] = useState<WaiverPriorityAdd[]>([]);
  const [neededPositions, setNeededPositions] = useState<string[]>([]);
  const [stashCandidates, setStashCandidates] = useState<WaiverPlayer[]>([]);
  const [watchlistCandidates, setWatchlistCandidates] = useState<WaiverPlayer[]>([]);
  const [faabTargets, setFaabTargets] = useState<WaiverPlayer[]>([]);
  const [isPremium, setIsPremium] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [position, setPosition] = useState('ALL');
  const [search, setSearch] = useState('');

  useScreenHeaderTitle(navigation, 'Waivers', leagueName);

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
          const result = await api.getLeagueWaivers(leagueId, { lens, limit: 300 });
          if (cancelled) return;
          setFreeAgents(result.players);
          setPriorityAdds(result.priority_adds);
          setNeededPositions(result.needed_positions);
          setStashCandidates(result.stash_candidates);
          setWatchlistCandidates(result.watchlist_candidates);
          setFaabTargets(result.faab_targets);
          setIsPremium(result.entitlement.is_premium);
          setNotice(result.reason ? reasonMessage(result.reason) : null);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load waivers.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId, lens]),
  );

  const filtered = useMemo(() => {
    if (!freeAgents) return [];
    const query = search.trim().toLowerCase();
    return freeAgents
      .filter((p) => position === 'ALL' || p.position === position)
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query));
  }, [freeAgents, position, search]);

  // Mirrors modules/waivers_ui.py's render_free_agent_summary_cards: prefer
  // non-stale players with a real score as the pool, falling back to the
  // full free-agent list only if nothing qualifies league-wide (not a
  // per-position fallback) — then the single top scorer per position, plus
  // how many active options exist at that position.
  const bestAvailable = useMemo(() => {
    if (!freeAgents || freeAgents.length === 0) return [];
    const activeAgents = freeAgents.filter((p) => !p.stale_free_agent && (p.score ?? 0) > 0);
    const source = activeAgents.length > 0 ? activeAgents : freeAgents;
    return BEST_AVAILABLE_POSITIONS.map((pos) => {
      const group = source.filter((p) => p.position === pos);
      if (group.length === 0) return null;
      const top = [...group].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
      return { position: pos, player: top, count: group.length };
    }).filter((entry): entry is { position: string; player: WaiverPlayer; count: number } => entry !== null);
  }, [freeAgents]);

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text={`Free agents ranked for your roster — ordered by fit for ${
          neededPositions.length > 0 ? `your needs at ${neededPositions.join(', ')}` : 'your team'
        }, not just raw value.`}
      />

      {notice ? <AppText style={styles.notice}>{notice}</AppText> : null}
      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <View style={styles.filterRow}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search free agents"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          placeholderTextColor={colors.textTertiary}
        />
      </View>
      <View style={styles.pillRow}>
        {POSITIONS.map((option) => (
          <TouchableOpacity
            key={option}
            style={[styles.pill, position === option && styles.pillActive]}
            onPress={() => setPosition(option)}
          >
            <AppText style={[styles.pillText, position === option && styles.pillTextActive]}>{option}</AppText>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <BrandedSpinner style={styles.loading} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          ListHeaderComponent={
            bestAvailable.length > 0 || priorityAdds.length > 0 ? (
              <View>
                {bestAvailable.length > 0 ? (
                  <View style={styles.bestAvailableBlock}>
                    <AppText style={styles.sectionLabel}>Best Available</AppText>
                    <View style={styles.bestAvailableRow}>
                      {bestAvailable.map(({ position: pos, player, count }) => (
                        <BestAvailableCard
                          key={pos}
                          position={pos}
                          player={player}
                          count={count}
                          onPress={() =>
                            navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })
                          }
                        />
                      ))}
                    </View>
                  </View>
                ) : null}
                {priorityAdds.length > 0 ? (
                  <View style={styles.priorityBlock}>
                    <AppText style={styles.sectionLabel}>Priority Adds</AppText>
                    {priorityAdds.map((player) => (
                      <PriorityAddCard
                        key={player.player_id}
                        player={player}
                        onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName })}
                      />
                    ))}
                  </View>
                ) : null}
                <AppText style={styles.sectionLabel}>All Free Agents</AppText>
              </View>
            ) : null
          }
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          ListHeaderComponentStyle={styles.listHeader}
          renderItem={({ item, index }) => (
            <WaiverCard
              player={item}
              rank={index + 1}
              topOfBoard={index === 0 && !search.trim()}
              onPress={() => navigation.navigate('PlayerDetail', { player: toRankedPlayer(item), leagueId, leagueName })}
            />
          )}
          ListEmptyComponent={
            <EmptyState
              icon="search-outline"
              title="No free agents match"
              subtitle="Try a different search term or position filter."
            />
          }
          ListFooterComponent={
            <SecondaryWaiverBoard
              isPremium={isPremium}
              stashCandidates={stashCandidates}
              watchlistCandidates={watchlistCandidates}
              faabTargets={faabTargets}
              leagueId={leagueId}
              leagueName={leagueName}
              navigation={navigation}
            />
          }
        />
      )}
    </View>
  );
}

// PlayerDetail's route param still expects the /rankings RankedPlayer shape
// (canonical_* ranks); waivers intentionally computes wire-relative ranks
// instead (see api.ts's WaiverPlayer doc comment), so this only forwards the
// fields Quick View actually reads rather than pretending the rank fields
// mean the same thing.
function toRankedPlayer(player: WaiverPlayer) {
  return {
    player_id: player.player_id,
    name: player.name,
    position: player.position,
    team: player.team,
    age: player.age,
    status: player.status,
    injury_status: player.injury_status,
    tier: player.tier,
    score: player.score,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
  };
}

function SecondaryWaiverBoard({
  isPremium,
  stashCandidates,
  watchlistCandidates,
  faabTargets,
  leagueId,
  leagueName,
  navigation,
}: {
  isPremium: boolean;
  stashCandidates: WaiverPlayer[];
  watchlistCandidates: WaiverPlayer[];
  faabTargets: WaiverPlayer[];
  leagueId: string;
  leagueName: string;
  navigation: Props['navigation'];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!isPremium) {
    return (
      <View style={styles.secondaryLockWrap}>
        <PremiumLock
          title="Full waiver board and FAAB shortlist"
          description="Priority Adds stay free — Premium adds stash candidates, watchlist depth, and a FAAB shortlist so you don't miss the next claim."
        />
      </View>
    );
  }
  if (stashCandidates.length === 0 && watchlistCandidates.length === 0 && faabTargets.length === 0) {
    return null;
  }
  const openPlayer = (player: WaiverPlayer) =>
    navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName });
  return (
    <View style={styles.secondaryBoard}>
      <AppText style={styles.secondaryCaption}>
        Upside stashes, watchlist depth, and a quick FAAB shortlist — check these after Priority Adds.
      </AppText>
      {stashCandidates.length > 0 ? (
        <View style={styles.priorityBlock}>
          <AppText style={styles.sectionLabel}>Stash Candidates</AppText>
          {stashCandidates.map((player, index) => (
            <WaiverCard key={player.player_id} player={player} rank={index + 1} onPress={() => openPlayer(player)} />
          ))}
        </View>
      ) : null}
      {watchlistCandidates.length > 0 ? (
        <View style={styles.priorityBlock}>
          <AppText style={styles.sectionLabel}>Watchlist Depth</AppText>
          {watchlistCandidates.map((player, index) => (
            <WaiverCard key={player.player_id} player={player} rank={index + 1} onPress={() => openPlayer(player)} />
          ))}
        </View>
      ) : null}
      {faabTargets.length > 0 ? (
        <View style={styles.priorityBlock}>
          <AppText style={styles.sectionLabel}>FAAB Shortlist</AppText>
          {faabTargets.map((player, index) => (
            <WaiverCard key={player.player_id} player={player} rank={index + 1} onPress={() => openPlayer(player)} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

function BestAvailableCard({
  position,
  player,
  count,
  onPress,
}: {
  position: string;
  player: WaiverPlayer;
  count: number;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <AnimatedCard style={styles.bestAvailableCard} onPress={onPress}>
      <View style={styles.bestAvailablePosBadge}>
        <AppText style={styles.bestAvailablePosText}>{position}</AppText>
      </View>
      <PlayerAvatar playerId={player.player_id} size={36} tier={player.tier} style={styles.avatarWrap} />
      <AppText style={styles.bestAvailableName} numberOfLines={1}>
        {player.name ?? 'Unknown'}
      </AppText>
      <AppText style={styles.bestAvailableScore}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
      <OverallRatingBadge rating={player.overall_rating} />
      <AppText style={styles.bestAvailableCount}>{count} active</AppText>
    </AnimatedCard>
  );
}

function PriorityAddCard({ player, onPress }: { player: WaiverPriorityAdd; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injuryColor = injuryPillColor(player.injury_status, colors);
  return (
    <AnimatedCard style={styles.priorityCard} onPress={onPress}>
      <View style={styles.priorityTopRow}>
        <Ionicons name="swap-horizontal-outline" size={14} color={colors.premium} />
        <AppText style={styles.priorityLabel}>{player.recommendation_label}</AppText>
      </View>
      <View style={styles.cardTopRow}>
        <PlayerAvatar playerId={player.player_id} size={44} tier={player.tier} style={styles.avatarWrap} />
        <View style={styles.nameColumn}>
          <AppText style={styles.name} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </AppText>
          <View style={styles.metaRow}>
            <PositionBadge position={player.position} />
            <AppText style={styles.meta} numberOfLines={1}>{player.team}</AppText>
            {opponentLabel(player) ? (
              <AppText style={styles.meta} numberOfLines={1}>{opponentLabel(player)}</AppText>
            ) : null}
          </View>
          {player.injury_replacement_fit ? (
            <AppText style={styles.injuryFitText}>{player.injury_replacement_note}</AppText>
          ) : injuryColor ? (
            <View style={styles.injuryRow}>
              <Ionicons name="medkit-outline" size={11} color={injuryColor} />
              <AppText style={[styles.injuryText, { color: injuryColor }]}>{player.injury_status}</AppText>
            </View>
          ) : null}
        </View>
        <View style={styles.valueColumn}>
          <AppText style={styles.valueNumber}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
          <TierBadge storedTier={player.tier} />
        </View>
      </View>
      <View style={styles.faabRow}>
        <View style={styles.faabInfo}>
          <Ionicons name="cash-outline" size={13} color={colors.textSecondary} />
          <AppText style={styles.faabText}>{player.faab.label}</AppText>
        </View>
        <View style={styles.detailPill}>
          <Ionicons name="information-circle-outline" size={12} color={colors.accentSoft} />
          <AppText style={styles.detailPillText}>Full breakdown</AppText>
        </View>
      </View>
    </AnimatedCard>
  );
}

function WaiverCard({
  player,
  rank,
  topOfBoard = false,
  onPress,
}: {
  player: WaiverPlayer;
  rank: number;
  /** Top of the All Free Agents board (a position filter still yields a
   * real #1 at that position; a search query doesn't) — gets the gold #1
   * rank badge (same premium hue as Teams' #1 power rank). Off for the
   * secondary Stash/Watchlist/FAAB lists, which each restart at 1. */
  topOfBoard?: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injuryColor = injuryPillColor(player.injury_status, colors);
  return (
    <AnimatedCard
      style={StyleSheet.flatten([styles.card, player.stale_free_agent && styles.cardStale])}
      onPress={onPress}
    >
      <View style={styles.cardTopRow}>
        <View style={styles.avatarWrap}>
          <PlayerAvatar playerId={player.player_id} size={44} tier={player.tier} />
          <View style={[styles.rankBadge, topOfBoard && styles.rankBadgeFirst]}>
            <AppText style={[styles.rankText, topOfBoard && styles.rankTextFirst]}>{rank}</AppText>
          </View>
        </View>
        <View style={styles.nameColumn}>
          <AppText style={styles.name} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </AppText>
          <View style={styles.metaRow}>
            <PositionBadge position={player.position} />
            <AppText style={styles.meta} numberOfLines={1}>{player.team}</AppText>
            {opponentLabel(player) ? (
              <AppText style={styles.meta} numberOfLines={1}>{opponentLabel(player)}</AppText>
            ) : null}
            {player.position_rank ? (
              <View style={styles.positionRankPill}>
                <AppText style={styles.positionRankText}>
                  {player.position}{player.position_rank}
                </AppText>
              </View>
            ) : null}
          </View>
          {player.injury_replacement_fit ? (
            <AppText style={styles.injuryFitText} numberOfLines={1}>{player.injury_replacement_note}</AppText>
          ) : injuryColor ? (
            <View style={styles.injuryRow}>
              <Ionicons name="medkit-outline" size={11} color={injuryColor} />
              <AppText style={[styles.injuryText, { color: injuryColor }]}>{player.injury_status}</AppText>
            </View>
          ) : null}
        </View>
        <View style={styles.valueColumn}>
          <AppText style={styles.valueNumber}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
          <AppText style={styles.valueLabel}>VALUE</AppText>
          <TierBadge storedTier={player.tier} />
        </View>
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  disclaimer: {
    fontSize: 12,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 16,
  },
  notice: {
    fontSize: 13,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  searchInput: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
  },
  filterRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  pillRow: {
    flexDirection: 'row',
    paddingHorizontal: spacing.lg,
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent, borderWidth: 1.5 },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff', fontWeight: '700' },
  loading: { marginTop: spacing.xl },
  listHeader: { marginBottom: spacing.sm },
  listContent: { padding: spacing.lg, paddingTop: 0, gap: spacing.sm },
  bestAvailableBlock: { gap: spacing.sm },
  bestAvailableRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  bestAvailableCard: {
    flexBasis: '30%',
    flexGrow: 1,
    padding: spacing.sm,
    alignItems: 'center',
    gap: 2,
  },
  bestAvailablePosBadge: {
    backgroundColor: colors.badgeBackground,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginBottom: spacing.xs,
  },
  bestAvailablePosText: { fontSize: 10, fontWeight: '700', color: colors.badgeText },
  bestAvailableName: { fontSize: 12, fontWeight: '600', color: colors.textPrimary, marginTop: spacing.xs },
  bestAvailableScore: { fontSize: 14, fontWeight: '700', color: colors.accent },
  bestAvailableCount: { fontSize: 10, color: colors.textTertiary },
  priorityBlock: { gap: spacing.sm },
  secondaryLockWrap: { marginTop: spacing.lg },
  secondaryBoard: { marginTop: spacing.lg, gap: spacing.md },
  secondaryCaption: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
  priorityCard: { padding: spacing.md, borderColor: colors.premium, borderWidth: 1 },
  priorityTopRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.xs },
  priorityLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.premium,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  faabRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.border,
  },
  faabInfo: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  faabText: { fontSize: 12, color: colors.textSecondary, fontWeight: '600' },
  // "Tap for full breakdown" affordance — makes it clear this priority-add
  // card leads to Player Quick View, not just a static reasoning label.
  detailPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  detailPillText: { fontSize: 10, fontWeight: '700', color: colors.accentSoft, letterSpacing: 0.2 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  card: { padding: spacing.md },
  cardStale: { opacity: 0.55 },
  cardTopRow: { flexDirection: 'row', alignItems: 'center' },
  avatarWrap: { marginRight: spacing.md },
  rankBadge: {
    position: 'absolute',
    top: -4,
    left: -4,
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.badgeBackground,
    borderWidth: 2,
    borderColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankText: { color: colors.badgeText, fontSize: 10, fontWeight: '700' },
  // #1 on the wire gets the premium/gold treatment (mirrors Teams' top
  // power rank) so the single best add reads at a glance in a long list.
  rankBadgeFirst: { backgroundColor: colors.premium },
  rankTextFirst: { color: colors.background },
  nameColumn: { flex: 1, marginRight: spacing.sm },
  name: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  meta: { fontSize: 12, color: colors.textSecondary, flexShrink: 1 },
  metaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  positionRankPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  injuryRow: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4 },
  injuryText: { fontSize: 11, fontWeight: '600', textTransform: 'capitalize' },
  injuryFitText: { fontSize: 11, fontWeight: '600', color: colors.accent, marginTop: 4 },
  valueColumn: { alignItems: 'flex-end', gap: 2 },
  valueNumber: { fontSize: 18, fontWeight: '700', color: colors.accent },
  valueLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
