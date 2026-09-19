import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, Modal, Pressable, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import TeamAvatar from '../components/TeamAvatar';
import PositionBadge from '../components/PositionBadge';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeValueHero from '../components/TradeValueHero';
import {
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
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
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
    opportunity_label: asset.opportunity_explanation ?? null,
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
      opportunity_label: asset.opportunity_explanation ?? null,
    }));
}

function ideaToShareVerdict(idea: TradeIdea): TradeVerdict {
  const gain = idea.trade_gain;
  const tone: TradeVerdict['tone'] = gain > 0 ? 'accept' : gain < 0 ? 'decline' : 'fair';
  return {
    band: idea.market_realism_label || 'Trade Hub idea',
    ui_verdict: tone === 'accept' ? 'ACCEPT' : tone === 'decline' ? 'DECLINE' : 'FAIR',
    confidence: idea.confidence_label || 'Low',
    rationale: idea.rationale,
    value_summary: `${gain > 0 ? '+' : ''}${gain} value vs ${idea.partner_team_name}`,
    roster_summary: idea.rationale,
    strategy_summary: idea.reasoning_tags.join(', ') || 'Generated by Trade Hub',
    risk_summary: `${idea.confidence_label || 'Low'} confidence · ${idea.market_realism_label || 'Thin'} market fit`,
    counter_guidance: '',
    fit_total: 0,
    value_delta: gain,
    tone,
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
  const [lens, setLens] = useState<ValuationLens>('Dynasty');

  useScreenHeaderTitle(navigation, 'Trade Hub', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <EvaluationLensHeaderButton lens={lens} onChange={setLens} />
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

  return (
    <View style={styles.root}>
      <GridBackground />
      <FlatList
      style={styles.container}
      data={loading || error || notReadyReason ? [] : ideas ?? []}
      keyExtractor={(_, index) => String(index)}
      contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}
      ListHeaderComponent={
        <View>
          <Text style={styles.disclaimer} numberOfLines={1}>
            Real ideas from the same engine and Trust checks as the web app's Trade Hub.
          </Text>
          {loading ? <ActivityIndicator style={styles.loading} color={colors.accent} /> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {notReadyReason ? (
            <Text style={styles.notReadyText}>
              {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build Trade Hub ideas for this league."}
            </Text>
          ) : null}
        </View>
      }
      renderItem={({ item }) => (
        <TradeIdeaCard idea={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      )}
      ListEmptyComponent={
        !loading && !error && !notReadyReason ? (
          <Text style={styles.empty}>
            No trade idea clears the bar for this strategy right now — check back after rosters move.
          </Text>
        ) : null
      }
      ListFooterComponent={
        !loading && !error && !notReadyReason && entitlement && entitlement.hidden_count > 0 ? (
          <TradeHubGateCard
            entitlement={entitlement}
            watchingAd={watchingAd}
            onWatchAd={onWatchAd}
            onUpgrade={() => navigation.navigate('Paywall')}
          />
        ) : null
      }
      />
    </View>
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
  const canWatchMoreAds = adsAvailable && entitlement.ad_unlocks_applied < entitlement.max_ad_unlocks;
  return (
    <AnimatedCard style={styles.gateCard}>
      <View style={styles.gateIconDisc}>
        <Ionicons name="lock-closed" size={20} color={colors.premium} />
      </View>
      <Text style={styles.gateTitle}>
        {entitlement.hidden_count} more {entitlement.hidden_count === 1 ? 'idea' : 'ideas'} on this board
      </Text>
      <Text style={styles.gateBody}>
        Free shows the top {entitlement.free_limit}. Watch a quick ad to reveal {entitlement.ad_bonus_per_unlock}{' '}
        more, or go Pro to unlock the full board.
      </Text>
      <View style={styles.gateButtonRow}>
        {canWatchMoreAds ? (
          <TouchableOpacity style={styles.gateSecondaryButton} onPress={onWatchAd} disabled={watchingAd}>
            {watchingAd ? (
              <ActivityIndicator size="small" color={colors.textPrimary} />
            ) : (
              <>
                <Ionicons name="play-circle-outline" size={16} color={colors.textPrimary} />
                <Text style={styles.gateSecondaryButtonText}>
                  Watch ad for +{entitlement.ad_bonus_per_unlock}
                </Text>
              </>
            )}
          </TouchableOpacity>
        ) : null}
        <TouchableOpacity style={styles.gatePrimaryButton} onPress={onUpgrade}>
          <Text style={styles.gatePrimaryButtonText}>Upgrade to Pro</Text>
        </TouchableOpacity>
      </View>
    </AnimatedCard>
  );
}

function AssetRow({
  asset,
  onPressPlayer,
  onPressPick,
}: {
  asset: PresentationAsset;
  onPressPlayer?: (asset: PresentationAsset) => void;
  onPressPick?: (asset: PresentationAsset) => void;
}) {
  if (asset.asset_type === 'pick') {
    const canOpenPick = Boolean(onPressPick && asset.pick_id);
    return (
      <TouchableOpacity
        style={styles.assetRow}
        disabled={!canOpenPick}
        activeOpacity={canOpenPick ? 0.7 : 1}
        onPress={() => onPressPick?.(asset)}
      >
        <View style={styles.pickDisc}>
          <Text style={styles.pickPlateText}>{asset.round ? `R${asset.round}` : 'PICK'}</Text>
        </View>
        <View style={styles.assetTextGroup}>
          <Text style={styles.assetName} numberOfLines={1}>
            {asset.label || 'Draft pick'}
          </Text>
          <Text style={styles.assetMeta} numberOfLines={1}>
            {asset.projected_range || 'Draft pick'}
          </Text>
        </View>
        {canOpenPick ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
      </TouchableOpacity>
    );
  }
  const metaLine = [asset.team, asset.age != null ? `Age ${asset.age}` : null].filter(Boolean).join(' · ');
  const canOpen = Boolean(onPressPlayer && asset.player_id);
  return (
    <TouchableOpacity
      style={styles.assetRow}
      disabled={!canOpen}
      activeOpacity={canOpen ? 0.7 : 1}
      onPress={() => onPressPlayer?.(asset)}
    >
      <PlayerAvatar playerId={asset.player_id} size={36} tier={asset.tier} style={styles.assetAvatar} />
      <View style={styles.assetTextGroup}>
        <Text style={styles.assetName} numberOfLines={1}>
          {asset.name ?? 'Unknown'}
        </Text>
        <View style={styles.assetMetaRow}>
          <PositionBadge position={asset.position} />
          <Text style={styles.assetMeta} numberOfLines={1}>
            {metaLine}
          </Text>
        </View>
        {asset.role ? (
          <Text style={styles.assetRole} numberOfLines={1}>
            {asset.role}
          </Text>
        ) : null}
        {asset.injury_status ? (
          <Text style={styles.assetInjury} numberOfLines={1}>
            {asset.injury_status}
          </Text>
        ) : null}
      </View>
      {canOpen ? <Ionicons name="chevron-forward" size={16} color={colors.textTertiary} /> : null}
    </TouchableOpacity>
  );
}

const VALUE_EDGE_BAND_COLOR: Record<string, string> = {
  Favorable: colors.success,
  Fair: colors.textSecondary,
  'Slight Overpay': colors.premium,
  'Major Overpay': colors.danger,
};

// modules/trade_hub_ui.py's trade_hub_display_section() taxonomy — mapped
// to the app's existing semantic palette (not a new color per category)
// so a scan down the Trade Hub feed reads as distinct idea types instead
// of one flat gray/blue-gray repeated on every card ("two-tone bluish
// gray... does not look good").
const CATEGORY_COLORS: Record<string, string> = {
  'Headline Recommendation': colors.accent,
  'Health Relief': colors.danger,
  'Draft Capital': colors.premium,
  'Age Optimization': colors.violet,
  Rebuild: colors.violet,
  Contender: colors.success,
  'Need-Based': colors.accentSoft,
  'High Confidence': colors.success,
};

function categoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? colors.textSecondary;
}

function CategoryBadge({ category }: { category: string }) {
  if (!category) return null;
  const color = categoryColor(category);
  return (
    <View style={[styles.categoryBadge, { backgroundColor: `${color}26`, borderColor: `${color}80` }]}>
      <Text style={[styles.categoryBadgeText, { color }]} numberOfLines={1}>
        {category.toUpperCase()}
      </Text>
    </View>
  );
}

function MeterRow({ label, value, level, color }: { label: string; value: string; level: number; color: string }) {
  return (
    <View style={styles.meter}>
      <Text style={styles.meterLabel}>{label}</Text>
      <View style={styles.meterSegments}>
        {[1, 2, 3].map((segment) => (
          <View
            key={segment}
            style={[styles.meterSegment, { backgroundColor: segment <= level ? color : colors.borderStrong }]}
          />
        ))}
      </View>
      <Text style={[styles.meterValue, { color }]}>{value}</Text>
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
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.rationaleBackdrop} onPress={onClose}>
        <Pressable style={styles.rationaleSheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.rationaleSheetHeader}>
            <Text style={styles.rationaleSheetTitle} numberOfLines={1}>
              Why this works
            </Text>
            <TouchableOpacity onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <Text style={styles.rationaleSheetPartner} numberOfLines={1}>
            vs. {partnerTeamName}
          </Text>
          <ScrollView style={styles.rationaleSheetBody}>
            <Text style={styles.rationaleSheetText}>{rationale}</Text>
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
  const { showExplanations } = useDensity();
  const confidenceLevel = CONFIDENCE_LEVELS[idea.confidence_label?.toLowerCase()] ?? 1;
  const realismLevel = REALISM_LEVELS[idea.market_realism_label?.toLowerCase()] ?? 1;
  const [shareOpen, setShareOpen] = useState(false);
  const [rationaleOpen, setRationaleOpen] = useState(false);
  const openPlayer = (asset: PresentationAsset) =>
    navigation.navigate('PlayerDetail', { player: assetToRankedPlayer(asset), leagueId, leagueName });
  const openPick = (asset: PresentationAsset) =>
    navigation.navigate('PickDetail', { pick: assetToDraftPick(asset), leagueId, leagueName });

  const bandColor = VALUE_EDGE_BAND_COLOR[idea.value_edge_band] ?? colors.textSecondary;

  const categoryAccent = categoryColor(idea.category);

  return (
    <AnimatedCard style={{ ...styles.card, borderLeftWidth: 3, borderLeftColor: categoryAccent }}>
      {idea.category ? (
        <View style={styles.categoryRow}>
          <CategoryBadge category={idea.category} />
        </View>
      ) : null}
      <View style={styles.partnerRow}>
        {idea.partner_team_avatar_url ? (
          <TeamAvatar avatarId={idea.partner_team_avatar_url} size={36} />
        ) : (
          <View style={styles.partnerAvatar}>
            <Text style={styles.partnerInitial}>{idea.partner_team_name.charAt(0).toUpperCase()}</Text>
          </View>
        )}
        <View style={styles.partnerTextGroup}>
          <Text style={styles.partnerName} numberOfLines={1}>
            {idea.partner_team_name}
          </Text>
        </View>
        <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
        </TouchableOpacity>
      </View>

      {/* Quick visual: the gain used to be a 14pt pill tucked beside the
          partner name, with the band on its own line below. Both now share
          one row led by the share card's big color-coded number, so a
          scrolling feed still gives each idea one scannable headline value
          without costing an extra row of height. */}
      <View style={styles.valueEdgeRow}>
        <TradeValueHero delta={idea.trade_gain} size="sm" />
        {idea.value_edge_band ? (
          <View style={[styles.valueEdgeChip, { borderColor: bandColor }]}>
            <Text style={[styles.valueEdgeText, { color: bandColor }]}>{idea.value_edge_band}</Text>
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
            <Text style={styles.exchangeLabel}>You Send</Text>
          </View>
          {idea.package.send.map((asset, index) => (
            <AssetRow key={`send-${index}`} asset={asset} onPressPlayer={openPlayer} onPressPick={openPick} />
          ))}
        </View>
        <View style={styles.exchangeGutter}>
          <View style={styles.swapDisc}>
            <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          </View>
        </View>
        <View style={styles.exchangeSide}>
          <View style={styles.exchangeLabelRow}>
            <View style={[styles.exchangeDot, { backgroundColor: colors.successBright }]} />
            <Text style={styles.exchangeLabel}>You Receive</Text>
          </View>
          {idea.package.receive.map((asset, index) => (
            <AssetRow key={`receive-${index}`} asset={asset} onPressPlayer={openPlayer} onPressPick={openPick} />
          ))}
        </View>
      </View>

      {showExplanations && idea.rationale ? (
        <TouchableOpacity activeOpacity={0.7} onPress={() => setRationaleOpen(true)}>
          <Text style={styles.rationaleLabel}>Why this works</Text>
          <Text style={styles.rationale} numberOfLines={3}>
            {idea.rationale}
          </Text>
          <Text style={styles.rationaleExpandHint}>Read full explanation</Text>
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

const styles = StyleSheet.create({
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
  loading: { marginVertical: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginTop: spacing.lg },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20, marginTop: spacing.xl },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl, lineHeight: 20 },
  card: { padding: 0, marginBottom: spacing.md },
  categoryRow: { paddingHorizontal: spacing.md, paddingTop: spacing.sm },
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
  valueEdgeRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  valueEdgeChip: {
    borderWidth: 1,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 1,
  },
  valueEdgeText: { fontSize: 10, fontWeight: '700' },
  pickPlateText: { fontSize: 11, fontWeight: '700', color: colors.premium },
  assetRole: { fontSize: 11, color: colors.accent, marginTop: 1 },
  assetInjury: { fontSize: 11, color: colors.danger, marginTop: 1 },
  partnerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
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
  partnerName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  shareButton: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  exchangeRow: { flexDirection: 'row', paddingHorizontal: spacing.md, gap: spacing.sm },
  exchangeSide: { flex: 1, gap: spacing.xs },
  exchangeGutter: { width: 28, alignItems: 'center', paddingTop: spacing.lg },
  swapDisc: {
    width: 28,
    height: 28,
    borderRadius: 14,
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
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  assetAvatar: {},
  pickDisc: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.backgroundElevated,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  rationaleLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    marginTop: spacing.md,
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
    borderColor: colors.border,
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
  footerRow: {
    flexDirection: 'row',
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
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
