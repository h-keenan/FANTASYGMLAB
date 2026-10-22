import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import AccentCard from './AccentCard';
import BeginnerHelp from './BeginnerHelp';
import MeterRow, { CONFIDENCE_LEVELS } from './ConfidenceMeter';
import DraftPickAssetRow from './DraftPickAssetRow';
import ManagerTendenciesChips from './ManagerTendenciesChips';
import PlayerCard from './PlayerCard';
import TeamAvatar from './TeamAvatar';
import ToneBadge from './ToneBadge';
import TradeSharePreviewModal from './TradeSharePreviewModal';
import TradeValueBar from './TradeValueBar';
import TradeValueHero from './TradeValueHero';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import type { DraftPickAsset, PresentationAsset, RankedPlayer, TradeIdea, TradeVerdict } from '../lib/api';
import { presentationAssetBackStats } from '../lib/playerCardBackStats';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type TradeHubNavigation = NativeStackNavigationProp<RootStackParamList>;

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
      // Was hardcoded null — harmless for the share PNG (it doesn't render
      // a score), but it silently meant Trade Hub-originated shares could
      // never carry a Trade Outcomes baseline value_score (see
      // TradeSharePreviewModal.recordShare), unlike Trade Analyzer's own
      // sendIds/receiveIds which already carry a real score. The idea's own
      // score is already computed under the same lens the idea was
      // generated with, so this is just passing existing data through.
      score: asset.score ?? null,
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


const REALISM_LEVELS: Record<string, number> = { realistic: 3, plausible: 2, thin: 1 };

/**
 * One side (You Send / You Receive) of a trade package: players render via
 * the shared, flippable `PlayerCard` (coridian_'s circled reference card,
 * generalized — see components/PlayerCard.tsx's own doc comment), picks
 * via DraftPickAssetRow — never a malformed player row for a pick. Order
 * is preserved exactly as the API returned it; only the per-asset
 * presentation differs by `asset_type`.
 *
 * `presentationAssetBackStats` (lib/playerCardBackStats.ts) builds each
 * player's back-face stats from fields `PresentationAsset` already carries
 * — tier, role, injury (status + severity), the asset's own value score,
 * team/age, and the role's rationale sentence — several of which
 * (`score`, `injury_level`, `opportunity_explanation`) had nowhere to
 * render on the old row at all. Tapping a player card now flips it instead
 * of navigating straight to Player Detail (PlayerIdentityRow's old
 * behavior) — `onOpenDetail` wires the card's own small corner affordance
 * to that navigation instead, matching coridian_'s ask that the primary
 * tap flip the card and a separate control open the PQV.
 *
 * Fixed `size` (not a flex-filled column width) deliberately mirrors
 * Waivers' `BestAvailableCard` sizing precedent — a trade side can carry
 * 2-3 assets, and a card stretched to the full exchange column's width
 * would read as oversized stacked repeatedly.
 */
export function ExchangeAssetList({
  assets,
  onPressPlayer,
  onPressPick,
}: {
  assets: PresentationAsset[];
  onPressPlayer: (asset: PresentationAsset) => void;
  onPressPick: (asset: PresentationAsset) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
      {assets.map((asset, index) => {
        const isLast = index === assets.length - 1;
        if (asset.asset_type === 'pick') {
          return (
            <View key={`pick-${asset.pick_id ?? index}`} style={!isLast && styles.exchangeItemSpacing}>
              <DraftPickAssetRow
                pickId={asset.pick_id}
                round={asset.round ? Number(asset.round) : null}
                label={asset.label}
                projectedRange={asset.projected_range}
                pickTier={asset.pick_tier}
                onPress={asset.pick_id ? () => onPressPick(asset) : undefined}
              />
            </View>
          );
        }
        const { note, stats } = presentationAssetBackStats(asset);
        return (
          <View key={`player-${asset.player_id ?? index}`} style={[styles.exchangeCardWrap, !isLast && styles.exchangeItemSpacing]}>
            <PlayerCard
              size={120}
              playerId={asset.player_id}
              name={asset.name}
              position={asset.position}
              tier={asset.tier}
              overallRating={asset.overall_rating}
              injuryLabel={asset.injury_status}
              backStats={stats}
              backNote={note}
              onOpenDetail={asset.player_id ? () => onPressPlayer(asset) : undefined}
            />
          </View>
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
  if (!category) return null;
  return <ToneBadge label={category} color={categoryColor(category, colors)} />;
}

// Semantic-color fix (recommendation-clarity audit, this pass): `sell_high`
// previously rendered in `colors.danger` (red). Per UI_MAGNA_CARTA.md §3,
// red is reserved app-wide for "injury, urgent risk, negative value, serious
// concern, unavailable/out states" — a Sell High tag is the opposite of
// that: it flags a *positive* strategic opportunity (this asset is
// appreciating, move it now), the same family as Buy Low. Coloring it red
// made a good-news recommendation look like a warning at a glance, directly
// undercutting "is it obvious what this recommendation is suggesting."
// `high_impact` moves from amber to cyan (primary GM-intelligence emphasis,
// matching the brief's "cyan = primary GM recommendation/intelligence") so
// it no longer collides with Sell High's new amber ("strategic
// opportunity/moderate caution," the same bucket Draft Capital already
// uses for a timing-sensitive move). Buy Low is unchanged — green already
// matched the spec. No underlying impact_tag/category values changed, only
// their display colors.
export type ImpactTagKey = 'high_impact' | 'buy_low' | 'sell_high';

export function impactTagConfig(
  colors: ThemeColors,
): Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> {
  return {
    high_impact: { label: 'High Impact', icon: 'flash', color: colors.accent },
    buy_low: { label: 'Buy Low', icon: 'trending-down', color: colors.success },
    sell_high: { label: 'Sell High', icon: 'trending-up', color: colors.premium },
  };
}


function ImpactBadge({ impactTag }: { impactTag: string }) {
  const { colors } = useThemeMode();
  const config = impactTagConfig(colors)[impactTag];
  if (!config) return null;
  return <ToneBadge label={config.label} color={config.color} />;
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
    <SheetModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.rationaleBackdrop} onPress={onClose}>
        <SwipeDismissCard style={styles.rationaleSheet} onDismiss={onClose}>
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
          <SheetScrollView style={styles.rationaleSheetBody}>
            <AppText style={styles.rationaleSheetText}>{rationale}</AppText>
          </SheetScrollView>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

export default function TradeIdeaCard({
  idea,
  leagueId,
  leagueName,
  navigation,
}: {
  idea: TradeIdea;
  leagueId: string;
  leagueName: string;
  navigation: TradeHubNavigation;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { showExplanations } = useDensity();
  const copy = useExperienceCopy();
  const confidenceLevel = CONFIDENCE_LEVELS[idea.confidence_label?.toLowerCase()] ?? 1;
  const realismLevel = REALISM_LEVELS[idea.market_realism_label?.toLowerCase()] ?? 1;
  const [shareOpen, setShareOpen] = useState(false);
  // Recorded alongside the share so the quiet Trade Outcomes result sweep
  // can re-value these same players under the same lens later.
  const { lens } = useValuationLens(leagueId);
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
    <AccentCard accent={categoryAccent} compact style={styles.card}>
      {idea.category || idea.impact_tag ? (
        <View style={[styles.categoryRow, styles.categoryRowSpread]}>
          <CategoryBadge category={idea.category} />
          <ImpactBadge impactTag={idea.impact_tag} />
        </View>
      ) : null}
      <BeginnerHelp text={copy.impactTagHelp(idea.impact_tag)} style={styles.beginnerHelp} />
      {/* Density fix (card-height audit, this pass): "Lands your target" and
          "FOR <team>" (All Trades mode only) previously each carried their
          own top padding as fully independent rows, stacking up to two
          extra half-rows of whitespace above the partner row before any
          trade content appeared. Both are lightweight context lines about
          who/why this idea exists, so they now share one tightly-spaced
          wrapper — still two distinct lines when both are present, nothing
          removed or merged in meaning, just less dead vertical space
          between them and above the partner identity that follows. */}
      {landedTargetNames.length > 0 || idea.source_team_name ? (
        <View style={styles.contextBlock}>
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
        </View>
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
            <AppText style={styles.partnerName} numberOfLines={2}>
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
          <ManagerTendenciesChips leagueId={leagueId} teamName={idea.partner_team_name} />
        </View>
        <TouchableOpacity
          style={styles.shareButton}
          onPress={() => setShareOpen(true)}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Share this trade"
        >
          <Ionicons name="share-outline" size={16} color={colors.accent} />
          <AppText style={styles.shareButtonText}>Share Trade</AppText>
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
      {/* Visual "who's winning" reinforcement for the number+pill above —
          same delta, same tradeValueColor mapping, just shape instead of
          just digits (UI_HIERARCHY_DIRECTIVE.md's "pair color with shape"). */}
      <TradeValueBar delta={idea.trade_gain} style={styles.valueBar} />
      <BeginnerHelp term="ideaBalance" style={styles.beginnerHelp} />

      <TradeSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueId={leagueId}
        leagueName={leagueName}
        partnerTeamName={idea.partner_team_name}
        partnerTeamAvatarUrl={idea.partner_team_avatar_url}
        sendTotal={idea.send_score}
        receiveTotal={idea.receive_score}
        verdict={ideaToShareVerdict(idea)}
        sendPlayers={shareAssetsToPlayers(idea.package.send)}
        receivePlayers={shareAssetsToPlayers(idea.package.receive)}
        valuationLens={lens}
      />

      <View style={styles.exchangeRow}>
        <View style={styles.exchangeSide}>
          <View style={styles.exchangeLabelRow}>
            <View style={[styles.exchangeDot, { backgroundColor: colors.danger }]} />
            <AppText style={styles.exchangeLabel}>You Send</AppText>
            {idea.send_score != null ? (
              <AppText style={styles.exchangeTotal}>{Math.round(idea.send_score).toLocaleString()}</AppText>
            ) : null}
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
            <AppText style={styles.exchangeLabel}>You Get</AppText>
            {idea.receive_score != null ? (
              <AppText style={styles.exchangeTotal}>{Math.round(idea.receive_score).toLocaleString()}</AppText>
            ) : null}
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
          <AppText style={styles.rationaleExpandHint}>View details</AppText>
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
        {idea.market_realism_label ? (
          <MeterRow
            label={copy.label('ideaRealism', 'REALISM').toUpperCase()}
            value={idea.market_realism_label}
            level={realismLevel}
            color={colors.premium}
          />
        ) : null}
      </View>
      <BeginnerHelp text={copy.help('ideaConfidence') && `Confidence: ${copy.help('ideaConfidence')}`} style={styles.beginnerHelp} />
      <BeginnerHelp text={copy.help('ideaRealism') && `Partner acceptance: ${copy.help('ideaRealism')}`} style={styles.beginnerHelp} />

      {/* Recommendation-clarity fix (this pass): every other required field
          on this card — partner, assets, value, rationale, confidence,
          realism — was already legible without an extra tap, but the card
          had no explicit, labeled action telling the user what to actually
          *do* about it. The only affordance for acting on an idea was the
          unlabeled share icon in the header above, which reads as "export a
          screenshot," not "this is how you propose this trade" — and
          nothing else on the card hints that sharing is the intended next
          step (Trade Hub can't submit a trade through Sleeper's API on the
          user's behalf, so a shareable trade card sent to the partner is
          the real, working path to actually act on a recommendation here).
          This button calls the exact same `setShareOpen` handler as the
          header icon — no new logic — just makes that path an explicit,
          full-width, clearly-labeled primary affordance at the natural end
          of the card, after the reasoning that justifies it. */}
      <TouchableOpacity
        style={styles.proposeButton}
        onPress={() => setShareOpen(true)}
        activeOpacity={0.85}
        accessibilityRole="button"
        accessibilityLabel="Share this trade to propose it"
      >
        <Ionicons name="paper-plane-outline" size={15} color={colors.background} />
        <AppText style={styles.proposeButtonText}>Share to Propose</AppText>
      </TouchableOpacity>
    </AccentCard>
  );
}


function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    beginnerHelp: { marginBottom: spacing.xs },
  card: { padding: 0, gap: 0, marginBottom: spacing.md },
  categoryRow: { paddingHorizontal: spacing.md, paddingTop: spacing.sm },
  categoryRowSpread: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
  // Both concept mockups show this as a quiet, thin-bordered box (no fill,
  // no title inside) rather than the hairline-top-rule-only treatment this
  // screen originally shipped with tonight — "keep the section visually
  // quiet" (brief section 3) still holds with an outline; it's the absence
  // of a heavy fill/shadow that keeps it quiet, not the absence of a border.
  contextBlock: { paddingHorizontal: spacing.md, paddingTop: spacing.xs, gap: 2 },
  landedTargetRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  landedTargetText: { fontSize: 11, fontWeight: '600', color: colors.premium, flexShrink: 1 },
  sourceTeamLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.6 },
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
    paddingBottom: spacing.xs,
    gap: spacing.sm,
  },
  valueHero: { flexShrink: 1 },
  valueBar: { marginHorizontal: spacing.md, marginBottom: spacing.sm },
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
  // Clearly visible secondary action: outlined accent, icon + label, 36pt+
  // target. The filled "Share to Propose" button below stays the primary.
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    minHeight: 36,
    paddingHorizontal: spacing.md,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.accent,
  },
  shareButtonText: { fontSize: 13, fontWeight: '700', color: colors.accent },
  exchangeRow: { flexDirection: 'row', paddingHorizontal: spacing.md, paddingBottom: spacing.xs, gap: spacing.sm },
  // Each side is its own small tinted surface (per section 6: "the
  // strongest visual element in the card") so PlayerIdentityRow/
  // DraftPickAssetRow's dividers have a clear boundary to sit inside of,
  // rather than floating on the card's bare background.
  //
  // Color-system audit follow-up (2026-10-08): this was `backgroundElevated`,
  // the same neutral-elevation token used for sheets/skeletons/input chrome.
  // In light mode that token (#D9E8F0) sits only ~1.1:1 contrast from
  // `background` (#EAF3F8) — both are desaturated pale blues — so the one
  // module the card most wants to pop (what you're actually trading) read as
  // flatter than plain neutral chrome. Switched to `accentMuted` (the token
  // already dedicated to "cyan tint over a surface," proven on
  // SegmentedTabBar's active pill) composited over the card's white
  // `surface`, plus the same `cardBorder` edge AnimatedCard already uses for
  // "this is a branded module" — a flat accentMuted fill alone measured
  // *less* distinct from white than the old backgroundElevated fill did, so
  // the border is what actually carries the separation. Only this role
  // changed; `backgroundElevated` itself is untouched and still backs every
  // genuine neutral-chrome use (gateSecondaryButton, partnerAvatar, swapDisc,
  // rationaleSheet, etc).
  exchangeSide: {
    flex: 1,
    backgroundColor: colors.accentMuted,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.xs,
    paddingBottom: 2,
  },
  // PlayerCard is square and fixed-size (see ExchangeAssetList's doc
  // comment) rather than stretched to the column's own flex:1 width, so
  // each tile needs its own flex-start wrapper inside the stretch-aligned
  // exchangeSide column.
  exchangeCardWrap: { alignSelf: 'flex-start' },
  exchangeItemSpacing: { marginBottom: spacing.sm },
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
  exchangeTotal: { marginLeft: 'auto', fontSize: 12, fontWeight: '800', color: colors.textSecondary },
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
    backgroundColor: scrim,
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
  // Primary CTA (recommendation-clarity fix): the one clearly-labeled,
  // real action affordance on the card. Reuses the same primary-button
  // visual language as `gatePrimaryButton` above (cyan fill, dark text) so
  // Trade Hub doesn't invent a second button style — cyan here reads as
  // "primary interaction" per Magna Carta §3/§17, not a value judgment on
  // the trade itself (a bad-value trade gets this exact same button; the
  // button proposes it, it doesn't endorse it).
  proposeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginHorizontal: spacing.md,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    paddingVertical: spacing.sm + 2,
    borderRadius: radii.md,
    backgroundColor: colors.accent,
  },
  proposeButtonText: { fontSize: 13, fontWeight: '700', color: colors.onAccent },
  });
}
