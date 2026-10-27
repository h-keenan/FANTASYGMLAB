import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from '../components/AppText';
import SectionHeading from '../components/SectionHeading';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import Button from '../components/Button';
import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import ExchangeSide from '../components/ExchangeSide';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAvatar from '../components/TeamAvatar';
import TradeValueHero from '../components/TradeValueHero';
import ValuesCredit from '../components/ValuesCredit';
import {
  api,
  type DraftPickAsset,
  type LineupPlayer,
  type PresentationAsset,
  type RankedPlayer,
  type TradeIdea,
} from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { useOrbClearance } from '../lib/orbLayout';
import { toUserErrorMessage } from '../lib/errorMessages';
import { TRADE_FINDER_MAX_PICKS, ownedPicksForRoster, toggleCappedSelection } from '../lib/tradeFinderPicks';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';

// Prop-driven now (TradesScreen owns the single `Trades` route and hosts
// this screen as one of its tabs) — leagueId/leagueName/navigation arrive as
// plain props instead of via route.params, but `navigation` is still the
// real root-stack navigation prop, used exactly as before for PlayerDetail/
// PickDetail.
type TradeFinderNavigation = NativeStackNavigationProp<RootStackParamList>;

interface Props {
  leagueId: string;
  leagueName: string;
  navigation: TradeFinderNavigation;
  /** PlayerDetail / Players "Find trades" (tap-depth audit #2): pre-selects
   * this player of yours once the roster loads and runs the search. */
  presetPlayerId?: string;
}

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };
const REALISM_LEVELS: Record<string, number> = { realistic: 3, plausible: 2, thin: 1 };

function valueEdgeBandColor(colors: ThemeColors): Record<string, string> {
  return {
    Favorable: colors.success,
    Fair: colors.textSecondary,
    'Slight Overpay': colors.premium,
    'Major Overpay': colors.danger,
  };
}

// Same shape adapters Trade Hub's idea feed uses to hand a lean
// PresentationAsset off to PlayerDetail/PickDetail — kept local to this
// screen (rather than imported from TradeHubScreen, which isn't a module
// other screens pull from) since they're small, pure display-shape shims,
// not shared business logic. PlayerDetail fetches its own real
// overall/position rank on mount, so those two fields are just placeholders
// here, same as Trade Hub.
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
 * One grouped, checkbox-led selection row — shared by the roster (player)
 * and pick lists so both selection groups read as the same control.
 */
function SelectableRow({
  selected,
  onToggle,
  isFirst,
  isLast,
  accessibilityLabel,
  disabled = false,
  children,
}: {
  selected: boolean;
  onToggle: () => void;
  isFirst: boolean;
  isLast: boolean;
  accessibilityLabel: string;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View
      style={[
        styles.rosterRow,
        isFirst && styles.rosterRowFirst,
        isLast && styles.rosterRowLast,
        !isLast && styles.rosterRowDivider,
        selected && styles.rosterRowSelected,
        disabled && styles.rosterRowDisabled,
      ]}
    >
      <TouchableOpacity
        onPress={onToggle}
        disabled={disabled}
        hitSlop={8}
        style={styles.checkboxTouch}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: selected, disabled }}
        accessibilityLabel={`${accessibilityLabel}${selected ? ', selected' : ''}`}
      >
        <View style={[styles.checkbox, selected && styles.checkboxChecked]}>
          {selected ? <Ionicons name="checkmark" size={14} color={colors.onAccent} /> : null}
        </View>
      </TouchableOpacity>
      <View style={styles.rosterIdentity}>{children}</View>
    </View>
  );
}

function PickSelectRow({
  pick,
  selected,
  disabled,
  onToggle,
  isFirst,
  isLast,
}: {
  pick: DraftPickAsset;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  return (
    <SelectableRow
      selected={selected}
      onToggle={onToggle}
      isFirst={isFirst}
      isLast={isLast}
      disabled={disabled}
      accessibilityLabel={pick.label ?? 'Draft pick'}
    >
      <DraftPickAssetRow
        pickId={pick.pick_id}
        round={pick.round}
        label={pick.label}
        projectedRange={pick.projected_pick_range}
        pickTier={pick.pick_tier}
        trailingValue={pick.score != null ? String(Math.round(pick.score)) : null}
        onPress={disabled ? undefined : onToggle}
        showDivider={false}
      />
    </SelectableRow>
  );
}

function RosterRow({
  player,
  selected,
  onToggle,
  isFirst,
  isLast,
}: {
  player: LineupPlayer;
  selected: boolean;
  onToggle: () => void;
  isFirst: boolean;
  isLast: boolean;
}) {
  return (
    <SelectableRow
      selected={selected}
      onToggle={onToggle}
      isFirst={isFirst}
      isLast={isLast}
      accessibilityLabel={player.name ?? 'Player'}
    >
      {/* overallRating matches Players/Waivers/GM Targets' rows (coridian_:
          player rows throughout the app need the same numeric Overall
          badge, not just a tier ring) — `overall_rating` was already on
          LineupPlayer, it just wasn't threaded into this row. No
          league-wide position-rank field exists on LineupPlayer, so no
          crown here (nothing to render honestly). */}
      <PlayerIdentityRow
        playerId={player.player_id}
        name={player.name}
        position={player.position}
        team={player.team}
        tier={player.tier}
        overallRating={player.overall_rating}
        injuryLabel={player.injury_label}
        ruledOut={player.ruled_out}
        onPress={onToggle}
        showDivider={false}
      />
    </SelectableRow>
  );
}

/**
 * A proposed trade for the selected players — the exact same TradeIdea shape
 * and card language Trade Hub's feed uses (§30: Send/Receive is a canonical
 * shared module), just for the on-demand set of results this specific
 * search returned rather than a passive, paginated board. No category/
 * impact-tag badges or share sheet here: those are Trade Hub *feed*
 * concepts (ranking/browsing many ideas over time), and don't add anything
 * to "here's what this exact selection could fetch."
 */
function ResultCard({
  idea,
  onPressPlayer,
  onPressPick,
}: {
  idea: TradeIdea;
  onPressPlayer: (asset: PresentationAsset) => void;
  onPressPick: (asset: PresentationAsset) => void;
}) {
  const { colors } = useThemeMode();
  const { showExplanations } = useDensity();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const confidenceLevel = CONFIDENCE_LEVELS[idea.confidence_label?.toLowerCase()] ?? 1;
  const realismLevel = REALISM_LEVELS[idea.market_realism_label?.toLowerCase()] ?? 1;
  const bandColor = valueEdgeBandColor(colors)[idea.value_edge_band] ?? colors.textSecondary;

  return (
    <AnimatedCard style={styles.resultCard}>
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
            {idea.value_edge_band ? (
              <View style={[styles.fairnessPill, { borderColor: bandColor }]}>
                <AppText style={[styles.fairnessPillText, { color: bandColor }]} numberOfLines={1}>
                  {idea.value_edge_band}
                </AppText>
              </View>
            ) : null}
          </View>
          {idea.partner_team_archetype_label ? (
            <AppText style={styles.partnerArchetype} numberOfLines={1}>
              {idea.partner_team_archetype_label}
            </AppText>
          ) : null}
        </View>
      </View>

      <TradeValueHero delta={idea.trade_gain} size="sm" style={styles.valueHero} />

      <View style={styles.exchangeRow}>
        <ExchangeSide
          side="send"
          assets={idea.package.send}
          onPressPlayer={onPressPlayer}
          onPressPick={onPressPick}
          style={styles.exchangeSide}
        />
        <View style={styles.exchangeGutter}>
          <View style={styles.swapDisc}>
            <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          </View>
        </View>
        <ExchangeSide
          side="get"
          assets={idea.package.receive}
          onPressPlayer={onPressPlayer}
          onPressPick={onPressPick}
          style={styles.exchangeSide}
        />
      </View>

      {showExplanations && idea.rationale ? (
        <>
          <AppText style={styles.rationaleLabel}>Why this works</AppText>
          <AppText style={styles.rationale} numberOfLines={4}>
            {idea.rationale}
          </AppText>
        </>
      ) : null}

      <View style={styles.footerRow}>
        <MeterRow label="CONFIDENCE" value={idea.confidence_label} level={confidenceLevel} color={colors.accent} />
        <MeterRow label="REALISM" value={idea.market_realism_label} level={realismLevel} color={colors.premium} />
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
export default function TradeFinderScreen({ leagueId, leagueName, navigation, presetPlayerId }: Props) {
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const orbClearance = useOrbClearance();

  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { strategy } = useGmStance(leagueId);
  const { lens } = useValuationLens(leagueId);

  const [roster, setRoster] = useState<LineupPlayer[]>([]);
  const [loadingRoster, setLoadingRoster] = useState(true);
  const [rosterError, setRosterError] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [ownedPicks, setOwnedPicks] = useState<DraftPickAsset[]>([]);
  const [selectedPickIds, setSelectedPickIds] = useState<Set<string>>(new Set());
  const [returnScope, setReturnScope] = useState<'any' | 'picks'>('any');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const result = await api.getLeagueMyTeam(leagueId, { lens });
          if (cancelled) return;
          if (result.reason) {
            setRosterError("Couldn't load your roster for this league.");
          } else if (result.trade_window?.trade_deadline_passed) {
            // Past the league's trade deadline Trade Finder stops searching
            // for in-season trades (GET .../my-team's additive trade_window).
            setRosterError(result.trade_window.message || 'Trade deadline has passed; trades reopen after the season.');
          } else {
            setRoster([...result.starters, ...result.bench]);
            // Your own picks to offer — GET .../draft-picks already reflects
            // Sleeper's traded-picks ownership. Never fatal: a failed pick
            // fetch just leaves player-only search.
            if (result.roster_id) {
              api
                .getLeagueDraftPicks(leagueId, { lens })
                .then((pickResult) => {
                  if (!cancelled) setOwnedPicks(ownedPicksForRoster(pickResult.picks ?? [], result.roster_id));
                })
                .catch(() => {});
            }
          }
        } catch (err) {
          if (!cancelled) setRosterError(toUserErrorMessage(err, 'Failed to load your roster.'));
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

  const togglePick = (pickId: string) => {
    setSelectedPickIds((prev) => toggleCappedSelection(prev, pickId));
    setIdeas(null);
  };

  const selectionCount = selectedIds.size + selectedPickIds.size;

  const search = async (playerIds: string[] = Array.from(selectedIds)) => {
    setSearchError(null);
    setSearching(true);
    try {
      const result = await api.getTradeFinderIdeas(leagueId, playerIds, strategy, lens, {
        pickIds: Array.from(selectedPickIds),
        returnPicks: returnScope === 'picks',
      });
      setIdeas(result.ideas);
      if (result.ideas.length === 0 && result.reason) {
        setSearchError(
          result.reason === 'no_players_selected'
            ? 'Select at least one player or pick to search with.'
            : result.reason === 'trade_deadline_passed'
              ? result.message || 'Trade deadline has passed; trades reopen after the season.'
              : "Couldn't search for trades right now.",
        );
      }
    } catch (err) {
      setSearchError(toUserErrorMessage(err, 'Could not search for trades.'));
    } finally {
      setSearching(false);
    }
  };

  // "Find trades" preset — once per player id, after the roster loads, and
  // only when the player really is on your roster (otherwise this is just
  // the normal empty builder). Free users get the same server response a
  // manual search would (this screen's existing gating, unchanged).
  const appliedPresetId = useRef<string | null>(null);
  useEffect(() => {
    if (loadingRoster || !presetPlayerId || appliedPresetId.current === presetPlayerId) return;
    appliedPresetId.current = presetPlayerId;
    if (!roster.some((p) => p.player_id === presetPlayerId)) return;
    setSelectedIds(new Set([presetPlayerId]));
    setSelectedPickIds(new Set());
    void search([presetPlayerId]);
    // `search` is recreated every render; the ref guard makes this one-shot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingRoster, presetPlayerId, roster]);

  const openPlayer = (asset: PresentationAsset) =>
    openQuickView(assetToRankedPlayer(asset), { leagueId, leagueName });
  const openPick = (asset: PresentationAsset) =>
    navigation.navigate('PickDetail', { pick: assetToDraftPick(asset), leagueId, leagueName });

  if (loadingRoster) {
    return <BrandedSpinner style={[styles.center]} />;
  }

  if (rosterError) {
    return (
      <View style={[styles.center]}>
        <AppText style={styles.error}>{rosterError}</AppText>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <GridBackground />
      <FlatList
        data={roster}
        keyExtractor={(item) => item.player_id}
        contentContainerStyle={[
          styles.listContent,
          { paddingTop: spacing.sm, paddingBottom: selectionCount > 0 ? spacing.lg : orbClearance + spacing.lg },
        ]}
        ListHeaderComponent={
          <View>
            <ScreenInfoNote
              text={`Pick the players and draft picks you'd actually consider moving — the engine searches every other roster in ${leagueName} for plausible trades built around exactly that selection.`}
            />
            <SectionHeading title="What You Want Back" topGap={12} />
            <SegmentedTabBar<'any' | 'picks'>
              options={[
                { key: 'any', label: 'Any return' },
                { key: 'picks', label: 'Picks back' },
              ]}
              active={returnScope}
              onChange={(key) => {
                setReturnScope(key);
                setIdeas(null);
              }}
            />
            {ideas !== null ? (
              <View style={styles.resultsSection}>
                <SectionHeading title={searching ? 'Searching…' : `${ideas.length} plausible trade${ideas.length === 1 ? '' : 's'} found`} topGap={12} />
                {searchError ? <AppText style={styles.error}>{searchError}</AppText> : null}
                {ideas.map((idea, index) => (
                  <ResultCard
                    key={`${idea.partner_team_name}-${index}`}
                    idea={idea}
                    onPressPlayer={openPlayer}
                    onPressPick={openPick}
                  />
                ))}
              </View>
            ) : searchError ? (
              <AppText style={styles.error}>{searchError}</AppText>
            ) : null}
            <SectionHeading title="Your Roster" topGap={12} />
          </View>
        }
        ListFooterComponent={
          <>
            {ownedPicks.length > 0 ? (
              <View>
                <SectionHeading title={`Your Picks (up to ${TRADE_FINDER_MAX_PICKS})`} topGap={12} />
                {ownedPicks.map((pick, index) => {
                  const selected = selectedPickIds.has(pick.pick_id);
                  return (
                    <PickSelectRow
                      key={pick.pick_id}
                      pick={pick}
                      selected={selected}
                      disabled={!selected && selectedPickIds.size >= TRADE_FINDER_MAX_PICKS}
                      onToggle={() => togglePick(pick.pick_id)}
                      isFirst={index === 0}
                      isLast={index === ownedPicks.length - 1}
                    />
                  );
                })}
              </View>
            ) : null}
            <ValuesCredit />
          </>
        }
        ListEmptyComponent={
          <EmptyState icon="people-outline" title="No roster found" subtitle="Nothing to shop yet in this league." />
        }
        renderItem={({ item, index }) => (
          <RosterRow
            player={item}
            selected={selectedIds.has(item.player_id)}
            onToggle={() => toggle(item.player_id)}
            isFirst={index === 0}
            isLast={index === roster.length - 1}
          />
        )}
      />

      {/* Sticky CTA bar (coridian_, 2026-10-24: the floating button covered
          roster rows). It is a normal flex sibling BELOW the list, not an
          absolute overlay, so the list simply ends above it and no row can
          be hidden. Hidden at zero selected (nothing to search). Bottom
          padding keeps the button clear of the GM Orb zone. */}
      {selectionCount > 0 ? (
        <View style={[styles.ctaBar, { paddingBottom: orbClearance + spacing.sm }]}>
          <Button label={`Find Trades (${selectionCount})`} loading={searching} onPress={() => search()} />
        </View>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: 'transparent' },
    center: {
      flex: 1,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'transparent',
      padding: spacing.xl,
    },
    // No `gap` here: the roster rows below need to render flush against
    // each other (hairline dividers, not gaps) to read as one continuous
    // grouped surface per section 12 — see `rosterRow`/`rosterRowDivider`.
    listContent: { padding: spacing.lg, paddingTop: 0 },
    sectionLabel: {
      fontSize: 12,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      marginTop: spacing.md,
      marginBottom: spacing.sm,
    },
    resultsSection: { marginBottom: spacing.sm },
    // Roster selection list: one continuous grouped surface with hairline
    // dividers between rows (Magna Carta section 12) instead of a bordered
    // card per player — only the group's own first/last row rounds the
    // corners, matching the canonical grouped-row pattern already used by
    // Waivers' free-agent table.
    rosterRow: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.glass,
      paddingHorizontal: spacing.md,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
    },
    rosterRowFirst: {
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopLeftRadius: radii.md,
      borderTopRightRadius: radii.md,
    },
    rosterRowLast: {
      borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
      borderBottomLeftRadius: radii.md,
      borderBottomRightRadius: radii.md,
    },
    rosterRowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    // Cyan is the app's fixed "selected state" semantic (section 3/14) — a
    // subtle tint on the row itself, not a fresh per-screen selection color.
    rosterRowSelected: { backgroundColor: colors.accentMuted },
    rosterRowDisabled: { opacity: 0.5 },
    checkboxTouch: { paddingVertical: spacing.sm, paddingRight: spacing.sm },
    checkbox: {
      width: 22,
      height: 22,
      borderRadius: radii.sm,
      borderWidth: 1.5,
      borderColor: colors.borderStrong,
      alignItems: 'center',
      justifyContent: 'center',
    },
    checkboxChecked: { backgroundColor: colors.accent, borderColor: colors.accent },
    rosterIdentity: { flex: 1 },
    resultCard: { padding: 0, marginBottom: spacing.sm },
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
      backgroundColor: colors.glassInset,
      alignItems: 'center',
      justifyContent: 'center',
    },
    partnerInitial: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    partnerTextGroup: { flex: 1 },
    partnerNameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    partnerName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary, flexShrink: 1 },
    partnerArchetype: { fontSize: 12, fontWeight: '500', color: colors.textSecondary, marginTop: 1 },
    fairnessPill: {
      flexShrink: 0,
      borderWidth: 1,
      borderRadius: radii.pill,
      paddingHorizontal: spacing.sm,
      paddingVertical: 1,
    },
    fairnessPillText: { fontSize: 10, fontWeight: '700' },
    valueHero: { paddingHorizontal: spacing.md, paddingBottom: spacing.sm },
    exchangeRow: { flexDirection: 'row', paddingHorizontal: spacing.md, paddingBottom: spacing.xs, gap: spacing.sm },
    // Each side is its own small tinted surface so PlayerIdentityRow/
    // DraftPickAssetRow's dividers have a clear boundary to sit inside of,
    // rather than floating on the card's bare background — same pattern
    // Trade Hub's idea feed uses for this exact content type.
    exchangeSide: { flex: 1 },
    exchangeGutter: { width: 26, alignItems: 'center', justifyContent: 'center' },
    swapDisc: {
      width: 26,
      height: 26,
      borderRadius: 13,
      backgroundColor: colors.glassInset,
      alignItems: 'center',
      justifyContent: 'center',
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
    ctaBar: {
      backgroundColor: colors.glass,
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopColor: colors.glassBorder,
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.sm,
    },
    error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
  });
}
