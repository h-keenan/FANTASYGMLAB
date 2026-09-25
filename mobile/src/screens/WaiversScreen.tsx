import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  FlatList,
  ScrollView,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import BrandHeaderBar from '../components/BrandHeaderBar';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import OverallRatingBadge from '../components/OverallRatingBadge';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PositionBadge from '../components/PositionBadge';
import PremiumLock from '../components/PremiumLock';
import PlayerAvatar from '../components/PlayerAvatar';
import ScreenInfoNote from '../components/ScreenInfoNote';
import WaiverRecommendationCard, {
  waiverInjuryDisplay,
  waiverOpponentContext,
} from '../components/WaiverRecommendationCard';
import { api, type WaiverPlayer, type WaiverPriorityAdd } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Waivers'>;

// K joins the filter chips alongside the four skill positions — the waiver
// pool already ranks kickers (see BEST_AVAILABLE_POSITIONS and the backend's
// own ["QB","RB","WR","TE","K"] enumeration in modules/waivers_ui.py), it was
// just missing from this chip row. DEF/DST is deliberately left out: the
// waiver pipeline doesn't surface team defenses at all, so a "DEF" chip
// would always render an empty list.
const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE', 'K'];
const BEST_AVAILABLE_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K'];

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

/** Section header used across every board on this screen — a plain
 * uppercase kicker plus an optional one-line caption underneath, replacing
 * a mix of ad hoc labels so "Priority Adds," "Best Available by Position,"
 * and "All Free Agents" all read as one family of section boundary. */
function SectionHeader({ label, caption }: { label: string; caption?: string | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.sectionHeaderWrap}>
      <AppText style={styles.sectionLabel}>{label}</AppText>
      {caption ? <AppText style={styles.sectionCaption}>{caption}</AppText> : null}
    </View>
  );
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

  const openPlayer = useCallback(
    (player: WaiverPlayer) => navigation.navigate('PlayerDetail', { player: toRankedPlayer(player), leagueId, leagueName }),
    [navigation, leagueId, leagueName],
  );

  const topPriority = priorityAdds[0] ?? null;
  const secondaryPriority = priorityAdds.length > 1 ? priorityAdds.slice(1) : [];
  const priorityCaption =
    neededPositions.length > 0
      ? `Personalized for your needs at ${neededPositions.join(', ')}`
      : 'Personalized for your roster';

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

      <View style={styles.discoveryCard}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search free agents"
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          placeholderTextColor={colors.textTertiary}
        />
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
      </View>

      {loading ? (
        <BrandedSpinner style={styles.loading} />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.player_id}
          ListHeaderComponent={
            <View>
              {topPriority ? (
                <View style={styles.sectionBlock}>
                  <SectionHeader label="Priority Adds" caption={priorityCaption} />
                  <WaiverRecommendationCard
                    player={topPriority}
                    variant="primary"
                    onPress={() => openPlayer(topPriority)}
                  />
                  {secondaryPriority.length > 0 ? (
                    <AnimatedCard style={styles.compactGroupCard}>
                      {secondaryPriority.map((player, index) => (
                        <WaiverRecommendationCard
                          key={player.player_id}
                          player={player}
                          variant="compact"
                          showDivider={index < secondaryPriority.length - 1}
                          onPress={() => openPlayer(player)}
                        />
                      ))}
                    </AnimatedCard>
                  ) : null}
                </View>
              ) : null}
              {bestAvailable.length > 0 ? (
                <View style={styles.sectionBlock}>
                  <SectionHeader label="Best Available by Position" />
                  <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.bestAvailableRow}>
                    {bestAvailable.map(({ position: pos, player, count }) => (
                      <BestAvailableCard key={pos} position={pos} player={player} count={count} onPress={() => openPlayer(player)} />
                    ))}
                  </ScrollView>
                </View>
              ) : null}
              <SectionHeader label="All Free Agents" />
            </View>
          }
          contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
          renderItem={({ item, index }) => (
            <FreeAgentRow
              player={item}
              rank={index + 1}
              isFirst={index === 0}
              isLast={index === filtered.length - 1}
              onPress={() => openPlayer(item)}
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
              onPressPlayer={openPlayer}
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
  onPressPlayer,
}: {
  isPremium: boolean;
  stashCandidates: WaiverPlayer[];
  watchlistCandidates: WaiverPlayer[];
  faabTargets: WaiverPlayer[];
  onPressPlayer: (player: WaiverPlayer) => void;
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
  const groups: Array<{ label: string; players: WaiverPlayer[] }> = [
    { label: 'Stash Candidates', players: stashCandidates },
    { label: 'Watchlist Depth', players: watchlistCandidates },
    { label: 'FAAB Shortlist', players: faabTargets },
  ].filter((group) => group.players.length > 0);
  return (
    <View style={styles.secondaryBoard}>
      <AppText style={styles.secondaryCaption}>
        Upside stashes, watchlist depth, and a quick FAAB shortlist — check these after Priority Adds.
      </AppText>
      {groups.map((group) => (
        <View key={group.label} style={styles.sectionBlock}>
          <SectionHeader label={group.label} />
          <AnimatedCard style={styles.compactGroupCard}>
            {group.players.map((player, index) => (
              <FreeAgentRow
                key={player.player_id}
                player={player}
                rank={index + 1}
                isFirst={index === 0}
                isLast={index === group.players.length - 1}
                bare
                onPress={() => onPressPlayer(player)}
              />
            ))}
          </AnimatedCard>
        </View>
      ))}
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
      {/* Shared PositionBadge (per-position semantic color, e.g. RB green /
          WR blue / TE orange) instead of a flat neutral pill — the concept
          gives each mini-card's position tag a distinct color, and
          PositionBadge is the app's one canonical source for that mapping
          (theme.ts positionColors), already used by every other player row
          on this same screen via PlayerIdentityRow. Wrapped so its own
          alignSelf:'flex-start' doesn't fight this card's centered layout. */}
      <View style={styles.bestAvailablePosBadgeWrap}>
        <PositionBadge position={position} size="md" />
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

/**
 * Dense free-agent row shared by "All Free Agents" and the secondary
 * Stash/Watchlist/FAAB boards below it — canonical PlayerIdentityRow for
 * identity, a slot chip carrying this list's own rank, and a trailing
 * value/position-rank column. `bare` drops the rank slot + grouped-table
 * edge borders for the secondary board, whose rows already sit inside their
 * own labeled AnimatedCard group rather than a single continuous table.
 */
function FreeAgentRow({
  player,
  rank,
  isFirst,
  isLast,
  bare = false,
  onPress,
}: {
  player: WaiverPlayer;
  rank: number;
  isFirst: boolean;
  isLast: boolean;
  bare?: boolean;
  onPress: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = player.injury_replacement_fit ? player.injury_replacement_note : waiverOpponentContext(player);
  return (
    <View
      style={[
        bare ? styles.freeAgentRowBare : styles.freeAgentRow,
        !bare && isFirst && styles.freeAgentRowFirst,
        !bare && isLast && styles.freeAgentRowLast,
        !isLast && styles.freeAgentDivider,
        player.stale_free_agent && styles.freeAgentStale,
      ]}
    >
      <View style={styles.freeAgentIdentity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          slot={bare ? undefined : String(rank)}
          injuryLabel={injury.label}
          injuryTone={injury.tone}
          ruledOut={injury.ruledOut}
          contextLine={contextLine}
          onPress={onPress}
          showDivider={false}
        />
      </View>
      <TouchableOpacity onPress={onPress} activeOpacity={0.7} style={styles.freeAgentTrailing}>
        <AppText style={styles.freeAgentValue}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        {player.position_rank ? (
          <View style={styles.positionRankPill}>
            <AppText style={styles.positionRankText}>
              {player.position}
              {player.position_rank}
            </AppText>
          </View>
        ) : null}
      </TouchableOpacity>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
  notice: {
    fontSize: 13,
    color: colors.textSecondary,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    lineHeight: 18,
  },
  discoveryCard: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    gap: spacing.sm,
  },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.background,
    color: colors.textPrimary,
  },
  pillRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.xs,
  },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent, borderWidth: 1.5 },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff', fontWeight: '700' },
  loading: { marginTop: spacing.xl },
  listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
  sectionBlock: { marginBottom: spacing.lg },
  sectionHeaderWrap: { marginBottom: spacing.sm, gap: 2 },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionCaption: { fontSize: 11.5, color: colors.textTertiary },
  compactGroupCard: { marginTop: spacing.sm, padding: spacing.sm },
  bestAvailableRow: { flexDirection: 'row', gap: spacing.sm, paddingRight: spacing.lg },
  bestAvailableCard: {
    width: 112,
    padding: spacing.sm,
    alignItems: 'center',
    gap: 2,
  },
  avatarWrap: { marginRight: spacing.md },
  bestAvailablePosBadgeWrap: { alignSelf: 'center', marginBottom: spacing.xs },
  bestAvailableName: { fontSize: 12, fontWeight: '600', color: colors.textPrimary, marginTop: spacing.xs },
  bestAvailableScore: { fontSize: 14, fontWeight: '700', color: colors.accent },
  bestAvailableCount: { fontSize: 10, color: colors.textTertiary },
  secondaryLockWrap: { marginTop: spacing.lg },
  secondaryBoard: { marginTop: spacing.lg },
  secondaryCaption: { fontSize: 12, color: colors.textSecondary, lineHeight: 16, marginBottom: spacing.md },
  freeAgentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
    borderRightWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
  },
  freeAgentRowBare: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  freeAgentRowFirst: {
    borderTopWidth: StyleSheet.hairlineWidth * 1.5,
    borderTopLeftRadius: radii.md,
    borderTopRightRadius: radii.md,
  },
  freeAgentRowLast: {
    borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
    borderBottomLeftRadius: radii.md,
    borderBottomRightRadius: radii.md,
  },
  freeAgentDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  freeAgentStale: { opacity: 0.55 },
  freeAgentIdentity: { flex: 1 },
  freeAgentTrailing: { alignItems: 'flex-end', gap: 2, paddingLeft: spacing.sm },
  freeAgentValue: { fontSize: 16, fontWeight: '700', color: colors.accent },
  positionRankPill: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  positionRankText: { fontSize: 10, fontWeight: '700', color: colors.textSecondary },
  error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
  });
}
