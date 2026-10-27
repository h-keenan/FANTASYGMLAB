import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import Button from '../components/Button';
import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import FilterDropdownButton from '../components/FilterDropdownButton';
import ErrorState from '../components/ErrorState';
import MeterRow, { CONFIDENCE_LEVELS } from '../components/ConfidenceMeter';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import GridBackground from '../components/GridBackground';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAvatar from '../components/TeamAvatar';
import ScreenInfoNote, { type ScreenInfoLegendItem } from '../components/ScreenInfoNote';
import FreeLimitNote from '../components/FreeLimitNote';
import BeginnerHelp from '../components/BeginnerHelp';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import SkeletonBlock, { SkeletonRow } from '../components/SkeletonBlock';
import ManagerTendenciesChips from '../components/ManagerTendenciesChips';
import DeadlineCard from '../components/DeadlineCard';
import TradeHubHoldCard from '../components/TradeHubHoldCard';
import TradeIdeaCard, { impactTagConfig, type ImpactTagKey } from '../components/TradeIdeaCard';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeValueBar from '../components/TradeValueBar';
import TradeValueHero from '../components/TradeValueHero';
import ValuesCredit from '../components/ValuesCredit';
import {
  type AllTradesEntitlement,
  type DraftPickAsset,
  type PresentationAsset,
  type RankedPlayer,
  type TeamStrategy,
  type TradeWindow,
  type TradeHubEntitlement,
  type TradeHubHold,
  type TradeIdea,
  type TradeVerdict,
  type ValuationLens,
} from '../lib/api';
import { api } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { toUserErrorMessage } from '../lib/errorMessages';
import { adsAvailable, showRewardedAd } from '../lib/ads';
import { useDensity } from '../context/DensityContext';
import { useGmStance } from '../context/GmStanceContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { useOrbClearance } from '../lib/orbLayout';
import { setSeenTradeIdeaCount } from '../lib/tradeHubSeen';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { SheetModal, SheetScrollView, SwipeDismissCard } from '../components/SwipeDismissSheet';

/**
 * Stand-in for a loading `TradeIdeaCard` — partner row (avatar + name/value
 * shape) plus a value-bar-shaped line, inside the same bordered card chrome
 * `TradeIdeaCard` itself renders in. Replaces the bare `ActivityIndicator`
 * that used to float alone above an otherwise-empty FlatList while the
 * first page of ideas was still loading (nothing below the header/tabs
 * hints at trade cards being on the way).
 */
function TradeIdeaSkeletonCard() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.card, styles.skeletonCard]}>
      <SkeletonRow />
      <SkeletonBlock height={36} style={styles.skeletonValueBlock} />
    </View>
  );
}

// Prop-driven now (TradesScreen owns the single `Trades` route and hosts
// this screen as one of its tabs) — leagueId/leagueName/navigation arrive as
// plain props instead of via route.params, but `navigation` is still the
// real root-stack navigation prop, used exactly as before for PlayerDetail/
// PickDetail/Paywall/TradeHistory.
type TradeHubNavigation = NativeStackNavigationProp<RootStackParamList>;

interface Props {
  leagueId: string;
  leagueName: string;
  navigation: TradeHubNavigation;
}


const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — Trade Hub needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_player_data: "Player data isn't available right now.",
  // modules/league_calendar.py's TRADE_DEADLINE_PASSED_MESSAGE.
  trade_deadline_passed: 'Trade deadline has passed; trades reopen after the season.',
};

export default function TradeHubScreen({ leagueId, leagueName, navigation }: Props) {
  const orbClearance = useOrbClearance();

  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // Read-only here: the header's GmStanceHeaderButton is the only place
  // stance is changed, and a change there re-runs `load` through this.
  const { strategy, loaded: stanceLoaded } = useGmStance(leagueId);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);
  const [entitlement, setEntitlement] = useState<TradeHubEntitlement | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [hold, setHold] = useState<TradeHubHold | null>(null);
  const [postureSentence, setPostureSentence] = useState('');
  const [tradeWindow, setTradeWindow] = useState<TradeWindow | undefined>(undefined);
  const [teamStrategy, setTeamStrategy] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adUnlocks, setAdUnlocks] = useState(0);
  const [watchingAd, setWatchingAd] = useState(false);
  // Filter chips in IdeaSummaryRow (null = "All" / the Trade Ideas total
  // tile). Client-side only — filters the same `ideas` the summary row
  // already counted, never re-requests or re-ranks anything.
  const [impactFilter, setImpactFilter] = useState<ImpactTagKey | null>(null);
  const [positionFilter, setPositionFilter] = useState<string | null>(null);
  const { lens } = useValuationLens(leagueId);

  // "All Trades" — the concept sheet's second Trade Hub tab: browse ideas
  // across every roster in the league, not just the caller's own. Kept as
  // fully separate state from "For You" above rather than reusing `ideas`,
  // since it's paginated (Load More) and never gets the ad-unlock gate
  // "For You" has — it has its own cumulative free-tier cap instead.
  const [viewMode, setViewMode] = useState<'for_you' | 'all_trades'>('for_you');
  const [allTradesIdeas, setAllTradesIdeas] = useState<TradeIdea[]>([]);
  const [allTradesCursor, setAllTradesCursor] = useState(0);
  const [allTradesHasMore, setAllTradesHasMore] = useState(false);
  const [allTradesEntitlement, setAllTradesEntitlement] = useState<AllTradesEntitlement | null>(null);
  const [allTradesLoading, setAllTradesLoading] = useState(false);
  const [allTradesLoadingMore, setAllTradesLoadingMore] = useState(false);
  const [allTradesError, setAllTradesError] = useState<string | null>(null);
  const [allTradesStarted, setAllTradesStarted] = useState(false);

  const load = useCallback(
    async (nextStrategy: TeamStrategy | 'auto', nextAdUnlocks: number, nextLens: ValuationLens) => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getTradeHubIdeas(leagueId, nextStrategy, nextAdUnlocks, nextLens);
        setHold(result.hold ?? null);
        setPostureSentence(result.posture_sentence ?? '');
        setTradeWindow(result.trade_window);
        setTeamStrategy(result.team_strategy);
        if (result.reason) {
          setNotReadyReason(result.reason);
          setIdeas(null);
          setEntitlement(null);
        } else {
          setNotReadyReason(null);
          setIdeas(result.ideas);
          setEntitlement(result.entitlement ?? null);
          void setSeenTradeIdeaCount(leagueId, result.ideas.length);
        }
      } catch (err) {
        setError(toUserErrorMessage(err, 'Failed to load Trade Hub ideas.'));
      } finally {
        setLoading(false);
      }
    },
    [leagueId],
  );

  // strategy=auto: the server resolves the declared stance itself (web does
  // the same), so the first fetch never waits on the stance fetch. A later
  // stance *change* still reloads; the initial unloaded -> loaded settle of
  // the stance context does not (the server already used that stance).
  const settledStrategy = stanceLoaded ? strategy : null;
  const lastSettledStrategy = useRef<TeamStrategy | null>(null);
  const hasRequested = useRef(false);
  useEffect(() => {
    const previous = lastSettledStrategy.current;
    lastSettledStrategy.current = settledStrategy;
    const isInitialSettle = hasRequested.current && previous === null && settledStrategy !== null;
    hasRequested.current = true;
    if (isInitialSettle) return;
    setAdUnlocks(0);
    setImpactFilter(null);
    void load('auto', 0, lens);
  }, [load, settledStrategy, lens]);

  const onWatchAd = useCallback(async () => {
    if (watchingAd) return;
    setWatchingAd(true);
    const earned = await showRewardedAd();
    setWatchingAd(false);
    if (!earned) return;
    const next = adUnlocks + 1;
    setAdUnlocks(next);
    void load('auto', next, lens);
  }, [adUnlocks, load, watchingAd, lens]);

  const loadAllTrades = useCallback(
    async (options: { reset: boolean }) => {
      const cursor = options.reset ? 0 : allTradesCursor;
      const shownCount = options.reset ? 0 : allTradesIdeas.length;
      if (options.reset) {
        setAllTradesLoading(true);
      } else {
        setAllTradesLoadingMore(true);
      }
      setAllTradesError(null);
      try {
        const result = await api.getAllTrades(leagueId, {
          strategy,
          lens,
          cursor,
          pageSize: 3,
          shownCount,
        });
        setAllTradesIdeas((prev) => (options.reset ? result.ideas : [...prev, ...result.ideas]));
        setAllTradesCursor(result.next_cursor);
        setAllTradesHasMore(result.has_more);
        setAllTradesEntitlement(result.entitlement);
      } catch (err) {
        setAllTradesError(toUserErrorMessage(err, 'Failed to load All Trades.'));
      } finally {
        setAllTradesLoading(false);
        setAllTradesLoadingMore(false);
      }
    },
    [leagueId, strategy, lens, allTradesCursor, allTradesIdeas.length],
  );

  const onSelectAllTrades = useCallback(() => {
    setViewMode('all_trades');
    if (!allTradesStarted) {
      setAllTradesStarted(true);
      void loadAllTrades({ reset: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allTradesStarted]);

  // Strategy/lens changed while All Trades has already been viewed once —
  // start over from the first page rather than silently keep stale ideas
  // generated under the old stance/lens.
  useEffect(() => {
    if (!allTradesStarted) return;
    setAllTradesIdeas([]);
    setAllTradesCursor(0);
    setAllTradesHasMore(false);
    void loadAllTrades({ reset: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategy, lens]);

  const isForYou = viewMode === 'for_you';
  // The deadline-passed state applies to the whole league, so it also
  // replaces All Trades' empty state rather than only For You's.
  const showNotReady = Boolean(notReadyReason && (isForYou || notReadyReason === 'trade_deadline_passed'));
  const activeLoading = isForYou ? loading : allTradesLoading;
  const activeError = isForYou ? error : allTradesError;
  // IdeaSummaryRow's chips filter this same `ideas` list by impact_tag —
  // client-side only, same data, same ranking, just a narrower view of it.
  const filteredIdeas = useMemo(() => {
    if (!ideas || (!impactFilter && !positionFilter)) return ideas;
    return ideas.filter(
      (idea) =>
        (!impactFilter || idea.impact_tag === impactFilter) &&
        (!positionFilter || ideaPositions(idea).includes(positionFilter)),
    );
  }, [ideas, impactFilter, positionFilter]);
  const activeData = isForYou
    ? activeLoading || activeError || notReadyReason
      ? []
      : filteredIdeas ?? []
    : allTradesIdeas;
  const impactFilterActiveWithNoResults = Boolean(
    isForYou && (impactFilter || positionFilter) && ideas && ideas.length > 0 && filteredIdeas && filteredIdeas.length === 0,
  );

  return (
    <View style={styles.root}>
      <GridBackground />
      <FlatList
      style={styles.container}
      data={activeData}
      keyExtractor={(_, index) => String(index)}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}
      ListHeaderComponent={
        <View>
          <View style={styles.viewModeRow}>
            <SegmentedTabBar<'for_you' | 'all_trades'>
              options={[
                { key: 'for_you', label: 'For You' },
                { key: 'all_trades', label: 'All Trades' },
              ]}
              active={viewMode}
              onChange={(key) => (key === 'for_you' ? setViewMode('for_you') : onSelectAllTrades())}
            />
          </View>
          <ScreenInfoNote
            text={
              isForYou
                ? 'Trust check: every idea is re-verified against your league’s live rosters right before it’s shown, so it can never suggest a player who’s since been traded, dropped, or picked up elsewhere.'
                : 'Real ideas across every roster in the league, not just yours.'
            }
            legend={isForYou ? impactLegend(colors) : undefined}
          />
          {isForYou && !activeLoading && !activeError && !notReadyReason && entitlement ? (
            <FreeLimitNote
              kind="window"
              noun="trade ideas"
              limit={entitlement.free_limit}
              total={entitlement.approved_count}
              shown={entitlement.visible_count}
              isPremium={entitlement.is_premium}
            />
          ) : null}
          {isForYou && !activeLoading && !activeError && !notReadyReason && ideas ? (
            <IdeaSummaryRow
              ideas={ideas}
              activeFilter={impactFilter}
              onToggleFilter={(next) => {
                trackUse('trade_hub_filters', 'filter_changed', {
                  props: { item_kind: 'impact', result: next ?? 'all' },
                });
                setImpactFilter(next);
              }}
            />
          ) : null}
          {isForYou && !activeLoading && !activeError && !notReadyReason && ideas ? (
            <PositionFilterRow
              ideas={ideas}
              active={positionFilter}
              onSelect={(next) => {
                trackUse('trade_hub_filters', 'filter_changed', {
                  props: { item_kind: 'position', result: next ?? 'all' },
                });
                setPositionFilter(next);
              }}
            />
          ) : null}
          {activeLoading ? (
            <View style={styles.skeletonWrap}>
              <TradeIdeaSkeletonCard />
              <TradeIdeaSkeletonCard />
              <TradeIdeaSkeletonCard />
            </View>
          ) : null}
          {activeError ? (
            <ErrorState
              title="Couldn't load trade ideas"
              message={activeError}
              onRetry={() => (isForYou ? void load('auto', adUnlocks, lens) : void loadAllTrades({ reset: true }))}
              compact
            />
          ) : null}
          {isForYou && !activeLoading && !activeError && postureSentence ? (
            <View style={styles.postureBlock}>
              <AppText style={styles.postureText}>{postureSentence}</AppText>
              <BeginnerHelp term="tradeHubPosture" />
            </View>
          ) : null}
          {isForYou && !activeLoading && !activeError ? (
            <DeadlineCard window={tradeWindow} strategy={teamStrategy} />
          ) : null}
          {isForYou && !activeLoading && !activeError && hold ? (
            <TradeHubHoldCard hold={hold} ideaCount={ideas?.length ?? 0} />
          ) : null}
          {showNotReady && !(hold && notReadyReason === 'trade_deadline_passed') ? (
            <EmptyState icon="time-outline" title="Not ready yet" subtitle={NOT_READY_MESSAGES[notReadyReason ?? ""] ?? "Couldn't build Trade Hub ideas for this league."} />
          ) : null}
        </View>
      }
      renderItem={({ item }) => (
        <TradeIdeaCard idea={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      )}
      ListEmptyComponent={
        !activeLoading && !activeError && !showNotReady && !(isForYou && hold && (ideas?.length ?? 0) === 0) ? (
          impactFilterActiveWithNoResults ? (
            <EmptyState
              icon="filter-outline"
              title={`No ${impactFilter ? impactTagConfig(colors)[impactFilter]?.label ?? 'matching' : positionFilter} ideas`}
              subtitle="Clear the filter above to see every trade idea for this strategy."
            />
          ) : (
            <EmptyState
              icon="shuffle-outline"
              title="No trades yet"
              subtitle={
                isForYou
                  ? 'No trade idea clears the bar for this strategy right now — check back after rosters move.'
                  : 'No trade idea cleared the bar for any team yet — check back after rosters move.'
              }
            />
          )
        ) : null
      }
      ListFooterComponent={
        <>
          {isForYou ? (
            !activeLoading && !activeError && !notReadyReason && entitlement && entitlement.hidden_count > 0 ? (
              <TradeHubGateCard
                entitlement={entitlement}
                watchingAd={watchingAd}
                onWatchAd={onWatchAd}
                onUpgrade={() => navigation.navigate('Paywall')}
              />
            ) : null
          ) : (
            <AllTradesFooter
              loadingMore={allTradesLoadingMore}
              hasMore={allTradesHasMore}
              entitlement={allTradesEntitlement}
              onLoadMore={() => void loadAllTrades({ reset: false })}
              onUpgrade={() => navigation.navigate('Paywall')}
            />
          )}
          <ValuesCredit />
        </>
      }
      />
    </View>
  );
}

function AllTradesFooter({
  loadingMore,
  hasMore,
  entitlement,
  onLoadMore,
  onUpgrade,
}: {
  loadingMore: boolean;
  hasMore: boolean;
  entitlement: AllTradesEntitlement | null;
  onLoadMore: () => void;
  onUpgrade: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (loadingMore) {
    return <TradeIdeaSkeletonCard />;
  }
  if (!hasMore) return null;
  const freeGated = Boolean(entitlement && !entitlement.is_premium && entitlement.remaining_free <= 0);
  if (freeGated) {
    return (
      <AnimatedCard style={styles.gateCard}>
        <View style={styles.gateIconDisc}>
          <Ionicons name="lock-closed" size={20} color={colors.premium} />
        </View>
        <AppText style={styles.gateTitle}>More teams to browse</AppText>
        <AppText style={styles.gateBody}>
          Free shows {entitlement?.free_limit} ideas across All Trades. Go Pro to browse every team.
        </AppText>
        <Button label="Upgrade to Pro" variant="premium" onPress={onUpgrade} style={styles.gatePrimaryButton} />
      </AnimatedCard>
    );
  }
  return (
    <Button label="Load More Teams" variant="secondary" onPress={onLoadMore} style={styles.loadMoreButton} />
  );
}

function TradeHubGateCard({
  entitlement,
  watchingAd,
  onWatchAd,
  onUpgrade,
}: {
  entitlement: TradeHubEntitlement;
  watchingAd: boolean;
  onWatchAd: () => void;
  onUpgrade: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const canWatchMoreAds = adsAvailable && entitlement.ad_unlocks_applied < entitlement.max_ad_unlocks;
  return (
    <AnimatedCard style={styles.gateCard}>
      <View style={styles.gateIconDisc}>
        <Ionicons name="lock-closed" size={20} color={colors.premium} />
      </View>
      <AppText style={styles.gateTitle}>
        {entitlement.hidden_count} more {entitlement.hidden_count === 1 ? 'idea' : 'ideas'} on this board
      </AppText>
      <AppText style={styles.gateBody}>
        Free shows the top {entitlement.free_limit}. Watch a quick ad to reveal {entitlement.ad_bonus_per_unlock}{' '}
        more, or go Pro to unlock the full board.
      </AppText>
      <View style={styles.gateButtonRow}>
        {canWatchMoreAds ? (
          <Button
            label={`Watch ad for +${entitlement.ad_bonus_per_unlock}`}
            variant="secondary"
            onPress={onWatchAd}
            loading={watchingAd}
            style={styles.gatePrimaryButton}
          />
        ) : null}
        <Button label="Upgrade to Pro" variant="premium" onPress={onUpgrade} style={styles.gatePrimaryButton} />
      </View>
    </AnimatedCard>
  );
}

// Legend shown inside Trade Hub's "About this screen" sheet. Definitions
// are sourced from the authoritative server logic, not invented copy:
// high_impact = confidence_label === "High" (trade_hub_engine.py's
// _classify_impact_tag); buy_low = the received asset carries a
// "Backup With Upside"/"Committee Back" opportunity_label
// (_BUY_LOW_OPPORTUNITY_LABELS — "role trending up, price probably hasn't
// caught up yet"); sell_high = the sent asset carries "Starter At Risk"
// (_SELL_HIGH_OPPORTUNITY_LABELS — established trade value from a starter
// reputation, but the opportunity signal underneath is already softening).
// Reuses impactTagConfig's exact labels/colors so the legend, the filter
// chips below, and each card's impact pill never drift from one another.
function impactLegend(colors: ThemeColors): ScreenInfoLegendItem[] {
  const config = impactTagConfig(colors);
  return [
    {
      label: config.high_impact.label,
      color: config.high_impact.color,
      description: "The model’s highest-confidence recommendation.",
    },
    {
      label: config.buy_low.label,
      color: config.buy_low.color,
      description: "You’d receive a player whose role is trending up before the market price catches up.",
    },
    {
      label: config.sell_high.label,
      color: config.sell_high.color,
      description: "You’d send a player whose trade value is still strong, but whose role has started to soften.",
    },
  ];
}

/** "12 Trade Ideas / 3 High Impact / 5 Buy Low / 4 Sell High" — a pure
 * client-side tally over the same ideas the list already renders, per the
 * concept sheet's Trade Hub summary row. Every count is real (impact_tag
 * is computed server-side from confidence_label/opportunity_label, not
 * invented here), so an idea with no tag just doesn't count toward any of
 * the three impact buckets — the total is still every idea's real total.
 *
 * Colors here intentionally match `impactTagConfig` below (see that
 * function's comment for the semantic-color fix applied in this pass).
 *
 * Each tile also doubles as a filter chip (this pass): tapping one filters
 * the idea list below to that impact_tag; tapping it again (or tapping
 * "Trade Ideas") clears back to "all." Active/inactive follows the same
 * cyan-emphasis-vs-quiet language as SegmentedTabBar's `segmentActive`
 * (accentMuted fill + accent border) rather than inventing a new chip
 * style — this never changes which ideas exist or how they're ranked,
 * only which of the already-loaded ideas render below. */
function IdeaSummaryRow({
  ideas,
  activeFilter,
  onToggleFilter,
}: {
  ideas: TradeIdea[];
  activeFilter: ImpactTagKey | null;
  onToggleFilter: (filter: ImpactTagKey | null) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const counts = useMemo(() => {
    let highImpact = 0;
    let buyLow = 0;
    let sellHigh = 0;
    for (const idea of ideas) {
      if (idea.impact_tag === 'high_impact') highImpact += 1;
      else if (idea.impact_tag === 'buy_low') buyLow += 1;
      else if (idea.impact_tag === 'sell_high') sellHigh += 1;
    }
    return { total: ideas.length, highImpact, buyLow, sellHigh };
  }, [ideas]);

  if (counts.total === 0) return null;

  const tiles: Array<{
    key: 'total' | ImpactTagKey;
    value: number;
    label: string;
    icon: keyof typeof Ionicons.glyphMap;
    color: string;
  }> = [
    { key: 'total', value: counts.total, label: 'Trade Ideas', icon: 'bulb-outline', color: colors.accent },
    { key: 'high_impact', value: counts.highImpact, label: 'High Impact', icon: 'flash', color: colors.accent },
    { key: 'buy_low', value: counts.buyLow, label: 'Buy Low', icon: 'trending-down', color: colors.success },
    { key: 'sell_high', value: counts.sellHigh, label: 'Sell High', icon: 'trending-up', color: colors.premium },
  ];

  return (
    <View style={styles.summaryBlock}>
      <View style={styles.summaryRow}>
        {tiles.map((tile) => {
          const isActive = tile.key === 'total' ? activeFilter === null : activeFilter === tile.key;
          return (
            <TouchableOpacity
              key={tile.key}
              style={[styles.summaryTile, isActive && styles.summaryTileActive]}
              activeOpacity={0.75}
              onPress={() =>
                onToggleFilter(
                  tile.key === 'total' ? null : activeFilter === tile.key ? null : (tile.key as ImpactTagKey),
                )
              }
              accessibilityRole="button"
              accessibilityState={{ selected: isActive }}
              accessibilityLabel={`Filter trade ideas by ${tile.label}`}
            >
              <Ionicons name={tile.icon} size={16} color={tile.color} />
              <AppText style={styles.summaryValue}>{tile.value}</AppText>
              <AppText style={styles.summaryLabel} numberOfLines={1}>{tile.label}</AppText>
            </TouchableOpacity>
          );
        })}
      </View>
    </View>
  );
}

const POSITION_ORDER = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DL', 'LB', 'DB'];

function ideaPositions(idea: TradeIdea): string[] {
  const seen = new Set<string>();
  for (const asset of [...idea.package.send, ...idea.package.receive]) {
    if (asset.asset_type === 'player' && asset.position) seen.add(asset.position);
  }
  return [...seen];
}

/** Positions filter chips (All + each position on the board). */
function PositionFilterRow({
  ideas,
  active,
  onSelect,
}: {
  ideas: TradeIdea[];
  active: string | null;
  onSelect: (position: string | null) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const positions = useMemo(() => {
    const all = new Set<string>();
    for (const idea of ideas) for (const pos of ideaPositions(idea)) all.add(pos);
    const rank = (pos: string) => (POSITION_ORDER.indexOf(pos) === -1 ? 99 : POSITION_ORDER.indexOf(pos));
    return [...all].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  }, [ideas]);
  if (positions.length < 2) return null;
  return (
    <View style={styles.positionChipRow}>
      <FilterDropdownButton
        label="Position"
        options={['ALL', ...positions]}
        value={active ?? 'ALL'}
        onChange={(next) => onSelect(next === 'ALL' ? null : next)}
      />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  gateCard: { alignItems: 'center', padding: spacing.lg, marginTop: spacing.xs },
  gateIconDisc: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.premiumMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  gateTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  gateBody: {
    fontSize: 12,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 18,
    marginTop: 4,
    marginBottom: spacing.md,
  },
  gateButtonRow: { flexDirection: 'row', gap: spacing.sm, width: '100%' },
  gatePrimaryButton: { flex: 1 },
  root: { flex: 1, backgroundColor: 'transparent' },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  disclaimer: { fontSize: 11, color: colors.textTertiary, marginBottom: spacing.md },
  viewModeRow: { marginBottom: spacing.sm },
  loadMoreButton: { alignSelf: 'center', marginTop: spacing.sm, marginBottom: spacing.xl, paddingHorizontal: spacing.xl },
  loading: { marginVertical: spacing.xl },
  skeletonWrap: { marginTop: spacing.sm },
  skeletonCard: { padding: spacing.md },
  skeletonValueBlock: { marginTop: spacing.md },
  postureBlock: { marginBottom: spacing.sm, gap: 2 },
  postureText: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20, marginTop: spacing.xl },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl, lineHeight: 20 },
  card: { padding: 0, marginBottom: spacing.md },
  summaryBlock: {
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  summaryRow: { flexDirection: 'row' },
  summaryTile: {
    flex: 1,
    alignItems: 'center',
    gap: 2,
    paddingVertical: spacing.xs,
    marginHorizontal: 2,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  // Filter-chip active state (this pass): same cyan-emphasis language as
  // SegmentedTabBar's `segmentActive` (accentMuted fill + accent border) —
  // reused rather than invented so "this chip is selected" reads
  // identically everywhere in the app.
  summaryTileActive: {
    backgroundColor: colors.accentMuted,
    borderColor: colors.accent,
  },
  summaryValue: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
  summaryLabel: { fontSize: 10, fontWeight: '600', color: colors.textSecondary, textAlign: 'center' },
  positionChipRow: { paddingBottom: spacing.md, alignItems: 'flex-start' },
  });
}
