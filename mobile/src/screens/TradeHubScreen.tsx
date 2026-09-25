import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, Modal, Pressable, ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EmptyState from '../components/EmptyState';
import BrandHeaderBar from '../components/BrandHeaderBar';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAvatar from '../components/TeamAvatar';
import ScreenInfoNote from '../components/ScreenInfoNote';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeValueHero from '../components/TradeValueHero';
import {
  type AllTradesEntitlement,
  type DraftPickAsset,
  type PresentationAsset,
  type RankedPlayer,
  type TeamStrategy,
  type TradeHubEntitlement,
  type TradeIdea,
  type TradeVerdict,
  type ValuationLens,
} from '../lib/api';
import { api } from '../lib/api';
import { adsAvailable, showRewardedAd } from '../lib/ads';
import { useDensity } from '../context/DensityContext';
import { useGmStance } from '../context/GmStanceContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { useOrbClearance } from '../lib/orbLayout';
import { setSeenTradeIdeaCount } from '../lib/tradeHubSeen';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

// PlayerDetail's route param still expects the /rankings RankedPlayer shape;
// Trade Hub only ever has the idea's own lean PresentationAsset, and
// PlayerDetail fetches the real overall/position rank itself on mount, so
// those two fields are just placeholders here.
function assetToRankedPlayer(asset: PresentationAsset): RankedPlayer {
  return {
    player_id: asset.player_id ?? '',
    name: asset.name ?? null,
    position: asset.position ?? null,
    team: asset.team ?? null,
    age: asset.age ?? null,
    status: null,
    injury_status: asset.injury_status ?? null,
    tier: asset.tier ?? null,
    score: asset.score ?? null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: asset.role ?? null,
  };
}

/** Trade Hub's AI-generated pick assets are the same PresentationAsset shape
 * Trade Analyzer's asset picker and Draft Center already turn into a tappable
 * PickDetail — they were just missing the identity/valuation fields until
 * modules/compact_fantasy_assets.py's presentation_asset() started including
 * them (pick_id, owner/original roster ids, the full multiplier breakdown).
 * PickDetailScreen degrades gracefully when the multiplier fields are absent
 * (its own `hasBreakdown` check), so a partial asset still renders fine. */
function assetToDraftPick(asset: PresentationAsset): DraftPickAsset {
  return {
    pick_id: asset.pick_id ?? '',
    label: asset.label ?? null,
    score: asset.score ?? null,
    season: asset.season ? Number(asset.season) : null,
    round: asset.round ? Number(asset.round) : null,
    original_roster_id: asset.original_roster_id ?? '',
    owner_roster_id: asset.owner_roster_id ?? '',
    original_team_name: asset.original_team_name ?? null,
    owner_team_name: asset.owner_team_name ?? null,
    pick_tier: asset.pick_tier ?? null,
    projected_pick_range: asset.projected_range ?? null,
    tier_bucket: asset.tier_bucket ?? null,
    base_score: asset.base_score ?? null,
    years_out: asset.years_out ?? null,
    future_discount: asset.future_discount ?? null,
    team_modifier: asset.team_modifier ?? null,
    format_multiplier: asset.format_multiplier ?? null,
    class_strength_multiplier: asset.class_strength_multiplier ?? null,
    prospect_strength_multiplier: asset.prospect_strength_multiplier ?? null,
    slot_percentile: asset.slot_percentile ?? null,
    projected_slot_percentile: asset.projected_slot_percentile ?? null,
    early_probability: asset.early_probability ?? null,
    mid_probability: asset.mid_probability ?? null,
    late_probability: asset.late_probability ?? null,
    projection_confidence: asset.projection_confidence ?? null,
    projection_source: asset.projection_source ?? null,
    is_current_year_pick: asset.is_current_year_pick ?? null,
  };
}

/** Trade Hub ideas don't carry a full RankedPlayer or TradeVerdict — both
 * are adapted here from the idea's own fields so the same share PNG
 * (built for Trade Analyzer's single-trade evaluation) can render a Trade
 * Hub idea too, without reshaping either shared component's contract. */
function shareAssetsToPlayers(assets: PresentationAsset[]): RankedPlayer[] {
  return assets
    .filter((asset) => asset.asset_type !== 'pick')
    .map((asset) => ({
      player_id: asset.player_id ?? '',
      name: asset.name ?? null,
      position: asset.position ?? null,
      team: asset.team ?? null,
      age: null,
      status: null,
      injury_status: null,
      tier: null,
      score: null,
      overall_rank: null,
      position_rank: null,
      rank_unavailable_reason: null,
      opportunity_label: asset.role ?? null,
    }));
}

function ideaToShareVerdict(idea: TradeIdea): TradeVerdict {
  const gain = idea.trade_gain;
  return {
    band: idea.market_realism_label || 'Trade Hub idea',
    // Always 'idea'/'IDEA' — this is a suggestion nobody has proposed or
    // acted on, not a real accept/decline verdict (coridian_: "it should
    // never say trade declined or trade accepted on the share sheet").
    // The value-change number below still colors green/red by sign.
    ui_verdict: 'IDEA',
    confidence: idea.confidence_label || 'Low',
    rationale: idea.rationale,
    value_summary: `${gain > 0 ? '+' : ''}${gain} value vs ${idea.partner_team_name}`,
    roster_summary: idea.rationale,
    strategy_summary: idea.reasoning_tags.join(', ') || 'Generated by Trade Hub',
    risk_summary: `${idea.confidence_label || 'Low'} confidence · ${idea.market_realism_label || 'Thin'} market fit`,
    counter_guidance: '',
    fit_total: 0,
    value_delta: gain,
    tone: 'idea',
  };
}

type Props = NativeStackScreenProps<RootStackParamList, 'TradeHub'>;

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };
const REALISM_LEVELS: Record<string, number> = { realistic: 3, plausible: 2, thin: 1 };

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — Trade Hub needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_player_data: "Player data isn't available right now.",
};

export default function TradeHubScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  // Read-only here: the header's GmStanceHeaderButton is the only place
  // stance is changed, and a change there re-runs `load` through this.
  const { strategy, loaded: stanceLoaded } = useGmStance(leagueId);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);
  const [entitlement, setEntitlement] = useState<TradeHubEntitlement | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adUnlocks, setAdUnlocks] = useState(0);
  const [watchingAd, setWatchingAd] = useState(false);
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

  useScreenHeaderTitle(navigation, 'Trade Hub', leagueName);

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
  }, [navigation, leagueId, lens]);

  const load = useCallback(
    async (nextStrategy: TeamStrategy, nextAdUnlocks: number, nextLens: ValuationLens) => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getTradeHubIdeas(leagueId, nextStrategy, nextAdUnlocks, nextLens);
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
        setError(err instanceof Error ? err.message : 'Failed to load Trade Hub ideas.');
      } finally {
        setLoading(false);
      }
    },
    [leagueId],
  );

  useEffect(() => {
    if (!stanceLoaded) return;
    setAdUnlocks(0);
    void load(strategy, 0, lens);
  }, [load, strategy, stanceLoaded, lens]);

  const onWatchAd = useCallback(async () => {
    if (watchingAd) return;
    setWatchingAd(true);
    const earned = await showRewardedAd();
    setWatchingAd(false);
    if (!earned) return;
    const next = adUnlocks + 1;
    setAdUnlocks(next);
    void load(strategy, next, lens);
  }, [adUnlocks, load, strategy, watchingAd, lens]);

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
        setAllTradesError(err instanceof Error ? err.message : 'Failed to load All Trades.');
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
  const activeLoading = isForYou ? loading : allTradesLoading;
  const activeError = isForYou ? error : allTradesError;
  const activeData = isForYou ? (activeLoading || activeError || notReadyReason ? [] : ideas ?? []) : allTradesIdeas;

  return (
    <View style={styles.root}>
      <GridBackground />
      <FlatList
      style={styles.container}
      data={activeData}
      keyExtractor={(_, index) => String(index)}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      ListHeaderComponent={
        <View>
          <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
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
                ? "Real ideas from the same engine and Trust checks as the web app's Trade Hub."
                : 'Real ideas across every roster in the league, not just yours.'
            }
          />
          {isForYou && !activeLoading && !activeError && !notReadyReason && ideas ? (
            <IdeaSummaryRow ideas={ideas} />
          ) : null}
          {activeLoading ? <ActivityIndicator style={styles.loading} color={colors.accent} /> : null}
          {activeError ? <AppText style={styles.error}>{activeError}</AppText> : null}
          {isForYou && notReadyReason ? (
            <AppText style={styles.notReadyText}>
              {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build Trade Hub ideas for this league."}
            </AppText>
          ) : null}
        </View>
      }
      renderItem={({ item }) => (
        <TradeIdeaCard idea={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      )}
      ListEmptyComponent={
        !activeLoading && !activeError && !(isForYou && notReadyReason) ? (
          <EmptyState
            icon="shuffle-outline"
            title="No trades yet"
            subtitle={
              isForYou
                ? 'No trade idea clears the bar for this strategy right now — check back after rosters move.'
                : 'No trade idea cleared the bar for any team yet — check back after rosters move.'
            }
          />
        ) : null
      }
      ListFooterComponent={
        isForYou ? (
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
        )
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
    return <ActivityIndicator style={styles.loading} color={colors.accent} />;
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
        <TouchableOpacity style={styles.gatePrimaryButton} onPress={onUpgrade}>
          <AppText style={styles.gatePrimaryButtonText}>Upgrade to Pro</AppText>
        </TouchableOpacity>
      </AnimatedCard>
    );
  }
  return (
    <TouchableOpacity style={styles.loadMoreButton} onPress={onLoadMore}>
      <AppText style={styles.loadMoreButtonText}>Load More Teams</AppText>
    </TouchableOpacity>
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
          <TouchableOpacity style={styles.gateSecondaryButton} onPress={onWatchAd} disabled={watchingAd}>
            {watchingAd ? (
              <ActivityIndicator size="small" color={colors.textPrimary} />
            ) : (
              <>
                <Ionicons name="play-circle-outline" size={16} color={colors.textPrimary} />
                <AppText style={styles.gateSecondaryButtonText}>
                  Watch ad for +{entitlement.ad_bonus_per_unlock}
                </AppText>
              </>
            )}
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity style={styles.gatePrimaryButton} onPress={onUpgrade}>
          <AppText style={styles.gatePrimaryButtonText}>Upgrade to Pro</AppText>
        </TouchableOpacity>
      </View>
    </AnimatedCard>
  );
}

/**
 * One side (You Send / You Receive) of a trade package: players render via
 * the shared PlayerIdentityRow (no `slot` — trade assets have no lineup
 * slot), picks via DraftPickAssetRow — never a malformed player row for a
 * pick. Order is preserved exactly as the API returned it; only the
 * per-asset presentation differs by `asset_type`.
 *
 * Team and age are combined into PlayerIdentityRow's single `team` slot
 * (e.g. "NO · Age 30") rather than passed separately (team) + via
 * `contextLine` (age) — the concept mockups show these on one meta line
 * under the position badge, not a whole extra row. This is a page-local
 * prop composition, not a change to PlayerIdentityRow itself: every other
 * screen using the shared row is unaffected.
 */
function ExchangeAssetList({
  assets,
  onPressPlayer,
  onPressPick,
}: {
  assets: PresentationAsset[];
  onPressPlayer: (asset: PresentationAsset) => void;
  onPressPick: (asset: PresentationAsset) => void;
}) {
  return (
    <>
      {assets.map((asset, index) => {
        const showDivider = index < assets.length - 1;
        if (asset.asset_type === 'pick') {
          return (
            <DraftPickAssetRow
              key={`pick-${asset.pick_id ?? index}`}
              pickId={asset.pick_id}
              round={asset.round ? Number(asset.round) : null}
              label={asset.label}
              projectedRange={asset.projected_range}
              pickTier={asset.pick_tier}
              onPress={asset.pick_id ? () => onPressPick(asset) : undefined}
              showDivider={showDivider}
            />
          );
        }
        const teamAgeLine = [asset.team, asset.age != null ? `Age ${asset.age}` : null]
          .filter(Boolean)
          .join(' · ');
        return (
          <PlayerIdentityRow
            key={`player-${asset.player_id ?? index}`}
            playerId={asset.player_id}
            name={asset.name}
            position={asset.position}
            team={teamAgeLine || null}
            tier={asset.tier}
            opportunityLabel={asset.role}
            injuryLabel={asset.injury_status}
            onPress={asset.player_id ? () => onPressPlayer(asset) : undefined}
            showDivider={showDivider}
          />
        );
      })}
    </>
  );
}

function valueEdgeBandColor(colors: ThemeColors): Record<string, string> {
  return {
    Favorable: colors.success,
    Fair: colors.textSecondary,
    'Slight Overpay': colors.premium,
    'Major Overpay': colors.danger,
  };
}

// modules/trade_hub_ui.py's trade_hub_display_section() taxonomy — mapped
// to the app's existing semantic palette (not a new color per category)
// so a scan down the Trade Hub feed reads as distinct idea types instead
// of one flat gray/blue-gray repeated on every card ("two-tone bluish
// gray... does not look good").
function categoryColors(colors: ThemeColors): Record<string, string> {
  return {
    'Headline Recommendation': colors.accent,
    'Health Relief': colors.danger,
    'Draft Capital': colors.premium,
    'Age Optimization': colors.violet,
    Rebuild: colors.violet,
    Contender: colors.success,
    'Need-Based': colors.accentSoft,
    'High Confidence': colors.success,
  };
}

function categoryColor(category: string, colors: ThemeColors): string {
  return categoryColors(colors)[category] ?? colors.textSecondary;
}

function CategoryBadge({ category }: { category: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!category) return null;
  const color = categoryColor(category, colors);
  return (
    <View style={[styles.categoryBadge, { backgroundColor: `${color}26`, borderColor: `${color}80` }]}>
      <AppText style={[styles.categoryBadgeText, { color }]} numberOfLines={1}>
        {category.toUpperCase()}
      </AppText>
    </View>
  );
}

function impactTagConfig(
  colors: ThemeColors,
): Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> {
  return {
    high_impact: { label: 'High Impact', icon: 'flash', color: colors.premium },
    buy_low: { label: 'Buy Low', icon: 'trending-down', color: colors.success },
    sell_high: { label: 'Sell High', icon: 'trending-up', color: colors.danger },
  };
}

function ImpactBadge({ impactTag }: { impactTag: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const config = impactTagConfig(colors)[impactTag];
  if (!config) return null;
  return (
    <View style={[styles.impactBadge, { borderColor: `${config.color}80` }]}>
      <Ionicons name={config.icon} size={11} color={config.color} />
      <AppText style={[styles.impactBadgeText, { color: config.color }]} numberOfLines={1}>
        {config.label.toUpperCase()}
      </AppText>
    </View>
  );
}

/** "12 Trade Ideas / 3 High Impact / 5 Buy Low / 4 Sell High" — a pure
 * client-side tally over the same ideas the list already renders, per the
 * concept sheet's Trade Hub summary row. Every count is real (impact_tag
 * is computed server-side from confidence_label/opportunity_label, not
 * invented here), so an idea with no tag just doesn't count toward any of
 * the three impact buckets — the total is still every idea's real total. */
function IdeaSummaryRow({ ideas }: { ideas: TradeIdea[] }) {
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

  const tiles: Array<{ key: string; value: number; label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = [
    { key: 'total', value: counts.total, label: 'Trade Ideas', icon: 'bulb-outline', color: colors.accent },
    { key: 'high_impact', value: counts.highImpact, label: 'High Impact', icon: 'flash', color: colors.premium },
    { key: 'buy_low', value: counts.buyLow, label: 'Buy Low', icon: 'trending-down', color: colors.success },
    { key: 'sell_high', value: counts.sellHigh, label: 'Sell High', icon: 'trending-up', color: colors.danger },
  ];

  return (
    <View style={styles.summaryBlock}>
      <View style={styles.summaryRow}>
        {tiles.map((tile) => (
          <View key={tile.key} style={styles.summaryTile}>
            <Ionicons name={tile.icon} size={16} color={tile.color} />
            <AppText style={styles.summaryValue}>{tile.value}</AppText>
            <AppText style={styles.summaryLabel} numberOfLines={1}>{tile.label}</AppText>
          </View>
        ))}
      </View>
    </View>
  );
}

function MeterRow({ label, value, level, color }: { label: string; value: string; level: number; color: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.meter}>
      <AppText style={styles.meterLabel}>{label}</AppText>
      <View style={styles.meterSegments}>
        {[1, 2, 3].map((segment) => (
          <View
            key={segment}
            style={[styles.meterSegment, { backgroundColor: segment <= level ? color : colors.borderStrong }]}
          />
        ))}
      </View>
      <AppText style={[styles.meterValue, { color }]}>{value}</AppText>
    </View>
  );
}

/**
 * The card's own rationale is clipped to 3 lines to keep the feed scannable
 * (see `styles.rationale`'s `numberOfLines={3}`) — this is the tap target
 * that surfaces the untruncated text, following the same backdrop-Pressable
 * shell RecapTradeDetailModal.tsx uses for "truncated on the card, full text
 * in a modal."
 */
function RationaleDetailModal({
  visible,
  onClose,
  partnerTeamName,
  rationale,
}: {
  visible: boolean;
  onClose: () => void;
  partnerTeamName: string;
  rationale: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.rationaleBackdrop} onPress={onClose}>
        <Pressable style={styles.rationaleSheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.rationaleSheetHeader}>
            <AppText style={styles.rationaleSheetTitle} numberOfLines={1}>
              Why this works
            </AppText>
            <TouchableOpacity onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <AppText style={styles.rationaleSheetPartner} numberOfLines={1}>
            vs. {partnerTeamName}
          </AppText>
          <ScrollView style={styles.rationaleSheetBody}>
            <AppText style={styles.rationaleSheetText}>{rationale}</AppText>
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function TradeIdeaCard({
  idea,
  leagueId,
  leagueName,
  navigation,
}: {
  idea: TradeIdea;
  leagueId: string;
  leagueName: string;
  navigation: Props['navigation'];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { showExplanations } = useDensity();
  const confidenceLevel = CONFIDENCE_LEVELS[idea.confidence_label?.toLowerCase()] ?? 1;
  const realismLevel = REALISM_LEVELS[idea.market_realism_label?.toLowerCase()] ?? 1;
  const [shareOpen, setShareOpen] = useState(false);
  const [rationaleOpen, setRationaleOpen] = useState(false);
  const openPlayer = (asset: PresentationAsset) =>
    navigation.navigate('PlayerDetail', { player: assetToRankedPlayer(asset), leagueId, leagueName });
  const openPick = (asset: PresentationAsset) =>
    navigation.navigate('PickDetail', { pick: assetToDraftPick(asset), leagueId, leagueName });

  const bandColor = valueEdgeBandColor(colors)[idea.value_edge_band] ?? colors.textSecondary;

  const categoryAccent = categoryColor(idea.category, colors);

  const landedTargetNames = (idea.landed_gm_target_player_ids ?? [])
    .map((playerId) => idea.package.receive.find((asset) => asset.player_id === playerId)?.name)
    .filter((name): name is string => Boolean(name));

  return (
    <AnimatedCard style={{ ...styles.card, borderLeftWidth: 3, borderLeftColor: categoryAccent }}>
      {idea.category || idea.impact_tag ? (
        <View style={[styles.categoryRow, styles.categoryRowSpread]}>
          <CategoryBadge category={idea.category} />
          <ImpactBadge impactTag={idea.impact_tag} />
        </View>
      ) : null}
      {landedTargetNames.length > 0 ? (
        <View style={styles.landedTargetRow}>
          <Ionicons name="locate" size={13} color={colors.premium} />
          <AppText style={styles.landedTargetText} numberOfLines={1}>
            Lands your target: {landedTargetNames.join(', ')}
          </AppText>
        </View>
      ) : null}
      {idea.source_team_name ? (
        <AppText style={styles.sourceTeamLabel} numberOfLines={1}>
          FOR {idea.source_team_name.toUpperCase()}
        </AppText>
      ) : null}
      {/* Header hierarchy: recommendation type (the category/impact badges
          above) -> team name + share action on one line -> value-change
          number prominently, paired with the fairness pill on its own row
          below. The original text-only redesign brief's suggested layout
          (section 5) put the fairness pill next to the team name, reasoning
          it as "secondary" (section 12) so it shouldn't compete with the
          headline value. The concept mockups (unavailable to that pass)
          consistently show it differently: a plain team-name+share row with
          no pill, and "Fair"/etc. riding right alongside the value number
          instead. Both mockups agree on this, so fidelity to the actual
          visual reference wins here — the pill stays small/quiet per
          section 12's intent, just relocated to match the images. */}
      <View style={styles.partnerRow}>
        {idea.partner_team_avatar_url ? (
          <TeamAvatar avatarId={idea.partner_team_avatar_url} size={36} />
        ) : (
          <View style={styles.partnerAvatar}>
            <AppText style={styles.partnerInitial}>{idea.partner_team_name.charAt(0).toUpperCase()}</AppText>
          </View>
        )}
        <View style={styles.partnerTextGroup}>
          <View style={styles.partnerNameRow}>
            <AppText style={styles.partnerName} numberOfLines={1}>
              {idea.partner_team_name}
            </AppText>
          </View>
          {idea.partner_team_archetype_label ? (
            <AppText style={styles.partnerArchetype} numberOfLines={1}>
              {idea.partner_team_archetype_label}
            </AppText>
          ) : null}
          {idea.partner_trade_tendency && idea.partner_trade_tendency !== 'Neutral' ? (
            <View style={styles.tendencyChip}>
              <Ionicons
                name={idea.partner_trade_tendency === 'Seller' ? 'trending-down' : 'trending-up'}
                size={10}
                color={idea.partner_trade_tendency === 'Seller' ? colors.accentSoft : colors.premium}
              />
              <AppText
                style={[
                  styles.tendencyChipText,
                  { color: idea.partner_trade_tendency === 'Seller' ? colors.accentSoft : colors.premium },
                ]}
                numberOfLines={1}
              >
                Real history of {idea.partner_trade_tendency === 'Seller' ? 'selling' : 'buying'}
              </AppText>
            </View>
          ) : null}
        </View>
        <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      <View style={styles.valueRow}>
        <TradeValueHero delta={idea.trade_gain} size="md" style={styles.valueHero} />
        {idea.value_edge_band ? (
          <View style={[styles.fairnessPill, { borderColor: bandColor }]}>
            <AppText style={[styles.fairnessPillText, { color: bandColor }]} numberOfLines={1}>
              {idea.value_edge_band}
            </AppText>
          </View>
        ) : null}
      </View>

      <TradeSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueId={leagueId}
        leagueName={leagueName}
        partnerTeamName={idea.partner_team_name}
        verdict={ideaToShareVerdict(idea)}
        sendPlayers={shareAssetsToPlayers(idea.package.send)}
        receivePlayers={shareAssetsToPlayers(idea.package.receive)}
      />

      <View style={styles.exchangeRow}>
        <View style={styles.exchangeSide}>
          <View style={styles.exchangeLabelRow}>
            <View style={[styles.exchangeDot, { backgroundColor: colors.danger }]} />
            <AppText style={styles.exchangeLabel}>You Send</AppText>
          </View>
          <ExchangeAssetList assets={idea.package.send} onPressPlayer={openPlayer} onPressPick={openPick} />
        </View>
        <View style={styles.exchangeGutter}>
          <View style={styles.swapDisc}>
            <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          </View>
        </View>
        <View style={styles.exchangeSide}>
          <View style={styles.exchangeLabelRow}>
            <View style={[styles.exchangeDot, { backgroundColor: colors.successBright }]} />
            <AppText style={styles.exchangeLabel}>You Receive</AppText>
          </View>
          <ExchangeAssetList assets={idea.package.receive} onPressPlayer={openPlayer} onPressPick={openPick} />
        </View>
      </View>

      {showExplanations && idea.rationale ? (
        <TouchableOpacity activeOpacity={0.7} onPress={() => setRationaleOpen(true)}>
          <AppText style={styles.rationaleLabel}>Why this works</AppText>
          <AppText style={styles.rationale} numberOfLines={3}>
            {idea.rationale}
          </AppText>
          <AppText style={styles.rationaleExpandHint}>Read full explanation</AppText>
        </TouchableOpacity>
      ) : null}

      <RationaleDetailModal
        visible={rationaleOpen}
        onClose={() => setRationaleOpen(false)}
        partnerTeamName={idea.partner_team_name}
        rationale={idea.rationale ?? ''}
      />

      <View style={styles.footerRow}>
        <MeterRow label="CONFIDENCE" value={idea.confidence_label} level={confidenceLevel} color={colors.accent} />
        <MeterRow label="REALISM" value={idea.market_realism_label} level={realismLevel} color={colors.premium} />
      </View>
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
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
  gateSecondaryButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.md,
    backgroundColor: colors.backgroundElevated,
  },
  gateSecondaryButtonText: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  gatePrimaryButton: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.md,
    backgroundColor: colors.accent,
  },
  gatePrimaryButtonText: { fontSize: 13, fontWeight: '700', color: colors.background },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  disclaimer: { fontSize: 11, color: colors.textTertiary, marginBottom: spacing.md },
  viewModeRow: { marginBottom: spacing.sm },
  loadMoreButton: {
    alignSelf: 'center',
    marginTop: spacing.sm,
    marginBottom: spacing.xl,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth * 1.5,
    borderColor: colors.cardBorder,
    backgroundColor: colors.surface,
  },
  loadMoreButtonText: { fontSize: 14, fontWeight: '700', color: colors.accent },
  loading: { marginVertical: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginTop: spacing.lg },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20, marginTop: spacing.xl },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl, lineHeight: 20 },
  card: { padding: 0, marginBottom: spacing.md },
  categoryRow: { paddingHorizontal: spacing.md, paddingTop: spacing.sm },
  categoryRowSpread: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  impactBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  impactBadgeText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  // Both concept mockups show this as a quiet, thin-bordered box (no fill,
  // no title inside) rather than the hairline-top-rule-only treatment this
  // screen originally shipped with tonight — "keep the section visually
  // quiet" (brief section 3) still holds with an outline; it's the absence
  // of a heavy fill/shadow that keeps it quiet, not the absence of a border.
  summaryBlock: {
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: radii.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  summaryRow: { flexDirection: 'row' },
  summaryTile: { flex: 1, alignItems: 'center', gap: 2 },
  summaryValue: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
  summaryLabel: { fontSize: 10, fontWeight: '600', color: colors.textSecondary, textAlign: 'center' },
  landedTargetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
  },
  landedTargetText: { fontSize: 11, fontWeight: '600', color: colors.premium, flexShrink: 1 },
  sourceTeamLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.6,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
  },
  categoryBadge: {
    alignSelf: 'flex-start',
    borderRadius: radii.sm,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  categoryBadgeText: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  // Value-change number + fairness pill share one row (per both concept
  // mockups: the pill rides alongside the value, not the team name) —
  // `valueRow` owns the card's horizontal padding so `valueHero` itself
  // stays unpadded and free to sit flush against the pill.
  valueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
  valueHero: { flexShrink: 1 },
  fairnessPill: {
    flexShrink: 0,
    borderWidth: 1,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
  },
  fairnessPillText: { fontSize: 12, fontWeight: '700' },
  partnerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
  partnerNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  partnerAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  partnerInitial: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  partnerTextGroup: { flex: 1 },
  partnerName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
  partnerArchetype: { fontSize: 12, fontWeight: '500', color: colors.textSecondary, marginTop: 1 },
  tendencyChip: { flexDirection: 'row', alignItems: 'center', gap: 3, marginTop: 2 },
  tendencyChipText: { fontSize: 11, fontWeight: '600' },
  // Plain icon per the concept mockups — no filled circular backdrop
  // (that read as an extra decorative surface neither concept image has).
  // hitSlop on the TouchableOpacity keeps the tap target comfortable
  // without a visible background box.
  shareButton: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  exchangeRow: { flexDirection: 'row', paddingHorizontal: spacing.md, paddingBottom: spacing.xs, gap: spacing.sm },
  // Each side is its own small tinted surface (per section 6: "the
  // strongest visual element in the card") so PlayerIdentityRow/
  // DraftPickAssetRow's dividers have a clear boundary to sit inside of,
  // rather than floating on the card's bare background.
  exchangeSide: {
    flex: 1,
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.xs,
    paddingBottom: 2,
  },
  exchangeGutter: { width: 26, alignItems: 'center', justifyContent: 'center' },
  swapDisc: {
    width: 26,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  exchangeLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 2 },
  exchangeDot: { width: 6, height: 6, borderRadius: 3 },
  exchangeLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  rationaleLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    marginTop: spacing.sm,
    marginBottom: 2,
  },
  rationale: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, paddingHorizontal: spacing.md },
  rationaleExpandHint: {
    fontSize: 11,
    fontWeight: '600',
    color: colors.accentSoft,
    paddingHorizontal: spacing.md,
    marginTop: 4,
  },
  rationaleBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  rationaleSheet: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    width: '100%',
    maxWidth: 420,
    maxHeight: '70%',
  },
  rationaleSheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  rationaleSheetTitle: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, flex: 1, marginRight: spacing.sm },
  rationaleSheetPartner: {
    fontSize: 12,
    color: colors.textTertiary,
    marginTop: 2,
    marginBottom: spacing.sm,
  },
  rationaleSheetBody: { flexGrow: 0 },
  rationaleSheetText: { fontSize: 14, color: colors.textSecondary, lineHeight: 20 },
  // Compact confidence/realism status strip (section 10): one shared
  // MeterRow component for both metrics, tight vertical padding so it reads
  // as a footer strip rather than a second content section.
  footerRow: {
    flexDirection: 'row',
    marginTop: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    gap: spacing.lg,
  },
  meter: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 14, height: 4, borderRadius: 2 },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  });
}
