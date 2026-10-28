import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import MeterRow, { confidenceLevelFor } from './ConfidenceMeter';
import FAABGuidance from './FAABGuidance';
import OverallRatingBadge from './OverallRatingBadge';
import PlayerIdentityRow from './PlayerIdentityRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { WaiverPriorityAdd } from '../lib/api';
import { waiverReasonChips } from '../lib/waiverChips';
import { injuryTone } from '../lib/injuryDisplay';
import { radii, spacing, type ThemeColors } from '../theme';


/** Same risk-vs-watch split WaiversScreen has always used, just relocated
 * next to the card that now owns injury presentation — "Out"-caliber
 * statuses get the solid/urgent pill (via PlayerIdentityRow's `ruledOut`),
 * "Questionable"-caliber statuses get the quieter amber `watch` tone, and
 * everything else renders no pill at all. Exported so WaiversScreen's plain
 * (non-priority) free-agent rows share the exact same classification
 * instead of re-deriving it. */
export function waiverInjuryDisplay(status: string | null): { label: string | null; tone: 'risk' | 'watch'; ruledOut: boolean } {
  const normalized = (status ?? '').trim().toLowerCase();
  if (!normalized) return { label: null, tone: 'risk', ruledOut: false };
  const label = status ? status.charAt(0).toUpperCase() + status.slice(1) : null;
  // The shared injury tone map decides: danger is the solid "ruled out" pill,
  // warning the amber watch pill, everything else no pill.
  const tone = injuryTone(normalized);
  if (tone === 'danger') return { label, tone: 'risk', ruledOut: true };
  if (tone === 'warning') return { label, tone: 'watch', ruledOut: false };
  return { label: null, tone: 'risk', ruledOut: false };
}

export function waiverOpponentContext(player: {
  opponent: string | null;
  opponent_is_home: boolean | null;
  opportunity_label?: string | null;
}): string | null {
  if (player.opponent) return `${player.opponent_is_home ? 'vs' : '@'} ${player.opponent}`;
  return player.opportunity_label ?? null;
}

/** Color override for `waiverOpponentContext`'s string when it's actually
 * showing the opponent (never for the opportunity_label fallback) — tough
 * defense (bad matchup for this free agent's position) reads danger/red,
 * weak defense (good matchup) reads success/green, average/unranked stays
 * the row's normal muted context color. Exact same tier→color mapping
 * Player Detail's Schedule tab already uses for this identical signal
 * (PlayerDetailScreen's `defenseTierColor`) — this is a restrained color
 * change to the existing text, not a new badge. */
export function waiverOpponentContextColor(
  player: { opponent: string | null; opponent_defense_tier?: 'tough' | 'average' | 'weak' | null },
  colors: ThemeColors,
): string | undefined {
  if (!player.opponent) return undefined;
  if (player.opponent_defense_tier === 'tough') return colors.danger;
  if (player.opponent_defense_tier === 'weak') return colors.success;
  return undefined;
}

/** Sleeper's GLOBAL (cross-league, last-24h) trending-add label for a free
 * agent, or null when the player isn't on Sleeper's trending-add list right
 * now. Deliberately says "Sleeper"/"across Sleeper," never "in your league"
 * — this is a platform-wide add-velocity signal, not anything scoped to
 * this league (see api.ts's WaiverPlayer.sleeper_trending_add doc comment).
 * Shared by WaiversScreen's plain free-agent rows and this card's own
 * identity row so both read the exact same label off PlayerIdentityRow. */
export function waiverTrendingAddLabel(player: {
  sleeper_trending_add?: boolean;
  sleeper_trending_add_count?: number | null;
}): string | null {
  if (!player.sleeper_trending_add) return null;
  const count = player.sleeper_trending_add_count;
  return count ? `Trending on Sleeper +${count.toLocaleString()}` : 'Trending on Sleeper';
}

// Concept-image fidelity: the concept shows a small colored classification
// pill (its mock copy: "IMPACT"/"STARTER") next to every recommendation's
// value number, including the secondary/compact rows below the top target.
// This app has no IMPACT/STARTER classification — waiver_recommendation_label
// in modules/waivers_ui.py only ever returns "Add"/"Stash"/"Watch" with tones
// "opportunity"/"information"/"neutral" — so the compact row below renders
// that real, already-fetched field/tone instead of inventing the mock's
// literal copy. (The primary/top-target card already surfaces this same
// field as its amber actionRow headline above, so it's deliberately not
// re-shown as a second pill there — that would just be the same
// classification said twice on the one card meant to say the least, loudest.)
// Tone -> color follows the Magna Carta semantic map: amber for
// "opportunity" (Section 3's "FAAB/acquisition context" bucket — a distinct
// use of amber from FAABGuidance's own dollar figure below, which is
// deliberately green per coridian_'s 2026-09-23 complaint that a bid read as
// a caution flag; this pill is the row's *action classification*, not the
// bid amount), cyan for "information" (analytical/GM-intelligence, e.g.
// "Stash"), and neutral slate as the fallback (e.g. "Watch").
function recommendationToneColor(tone: string, colors: ThemeColors): string {
  if (tone === 'opportunity') return colors.premium;
  if (tone === 'information') return colors.accent;
  return colors.textSecondary;
}

function RecommendationPill({ label, tone }: { label: string | null; tone: string | null }) {
  const { colors } = useThemeMode();
  if (!label) return null;
  const color = recommendationToneColor(tone ?? 'neutral', colors);
  return (
    <View style={[pillStyles.badge, { backgroundColor: `${color}26`, borderColor: `${color}70` }]}>
      <AppText style={[pillStyles.text, { color }]} numberOfLines={1}>
        {label}
      </AppText>
    </View>
  );
}

const pillStyles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 1,
  },
  text: { fontSize: 9, fontWeight: '800', letterSpacing: 0.3, textTransform: 'uppercase' },
});

/** Up to two reason chips from real, already-computed signals only
 * (lib/waiverChips.ts); renders nothing when none apply. */
function ReasonChips({ player }: { player: WaiverPriorityAdd }) {
  const { colors } = useThemeMode();
  const chips = waiverReasonChips(player);
  if (chips.length === 0) return null;
  return (
    <View style={chipStyles.row}>
      {chips.map((chip) => (
        <View key={chip} style={[chipStyles.chip, { borderColor: `${colors.accent}70`, backgroundColor: `${colors.accent}1A` }]}>
          <AppText style={[chipStyles.text, { color: colors.accent }]} numberOfLines={1}>
            {chip}
          </AppText>
        </View>
      ))}
    </View>
  );
}

const chipStyles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  chip: { borderRadius: radii.pill, borderWidth: 1, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  text: { fontSize: 11, fontWeight: '700' },
});

/**
 * Canonical waiver recommendation card — backs both the single "Top Waiver
 * Target" (variant="primary": full glowing AnimatedCard, the loudest thing
 * on the screen) and every subsequent Priority Add (variant="compact": a
 * plain dense row meant to sit inside one shared surface with other compact
 * rows, separated by `showDivider`, so a run of recommendations doesn't
 * repeat a bordered card per player). Both variants share identical data
 * plumbing (identity, value, injury, FAAB, Full Breakdown) so they can never
 * drift apart on what a recommendation actually shows.
 */
export default function WaiverRecommendationCard({
  player,
  onPress,
  variant = 'compact',
  showDivider = false,
  rank,
}: {
  player: WaiverPriorityAdd;
  onPress: () => void;
  variant?: 'primary' | 'compact';
  showDivider?: boolean;
  /** Position in the recommendation list (compact rows: 2, 3, ...). */
  rank?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = player.injury_replacement_fit ? player.injury_replacement_note : waiverOpponentContext(player);
  const contextLineColor = player.injury_replacement_fit ? undefined : waiverOpponentContextColor(player, colors);
  const isPrimary = variant === 'primary';

  const identity = (
    <PlayerIdentityRow
      playerId={player.player_id}
      name={player.name}
      position={player.position}
      team={player.team}
      tier={player.tier}
      injuryLabel={injury.label}
      injuryTone={injury.tone}
      ruledOut={injury.ruledOut}
      contextLine={contextLine}
      contextLineColor={contextLineColor}
      trendingAddLabel={waiverTrendingAddLabel(player)}
      slot={rank != null ? String(rank) : undefined}
      showDivider={false}
    />
  );

  if (isPrimary) {
    return (
      <AnimatedCard glow style={styles.primaryCard} onPress={onPress}>
        <View style={styles.actionRow}>
          <Ionicons name="swap-horizontal-outline" size={13} color={colors.premium} />
          <AppText style={styles.actionLabel}>{player.recommendation_label} · Top Waiver Target</AppText>
        </View>
        <View style={styles.identityWrap}>{identity}</View>
        <ReasonChips player={player} />
        <View style={styles.metricsRow}>
          <View style={styles.scoreBlock}>
            <AppText style={styles.scoreNumberPrimary}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
            <AppText style={styles.scoreLabel}>VALUE</AppText>
          </View>
          <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} size="md" />
          <View style={styles.metricsDivider} />
          <FAABGuidance faab={player.faab} size="prominent" />
        </View>
        {/* Evidence-backed "why" for the bid (or the claim guidance in
            non-FAAB leagues) — modules/faab.py FaabGuidance.why. */}
        {player.faab?.why ? (
          <AppText style={styles.faabWhy} numberOfLines={3}>
            {player.faab.why}
          </AppText>
        ) : null}
        {/* Beginner-only explanations (lib/experienceCopy.ts); nothing renders
            for advanced/unset accounts. Primary card only, so the compact
            rows below stay as dense as before. */}
        <BeginnerHelp term="waiverValue" style={styles.beginnerHelp} />
        <BeginnerHelp term="faab" style={styles.beginnerHelp} />
        {/* Real need-fit/standout-value confidence for this recommendation
            (modules.waivers_ui.waiver_confidence_label) — the same signals
            that ranked it into Priority Adds, shown with the exact same
            segmented-meter pattern Trade Hub's own confidence display uses. */}
        <View style={styles.confidenceRow}>
          {player.confidence_label ? (
            <View style={styles.confidenceMeter}>
              <MeterRow
                label="CONFIDENCE"
                value={player.confidence_label}
                level={confidenceLevelFor(player.confidence_label)}
                color={colors.premium}
              />
            </View>
          ) : (
            <View style={styles.confidenceMeter} />
          )}
          <TouchableOpacity
            style={styles.detailsButton}
            onPress={onPress}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel={`View details for ${player.name ?? 'player'}`}
          >
            <AppText style={styles.detailsButtonText}>View details</AppText>
            <Ionicons name="arrow-forward" size={14} color={colors.accent} />
          </TouchableOpacity>
        </View>
        {player.confidence_label ? <BeginnerHelp term="waiverConfidence" style={styles.beginnerHelp} /> : null}
      </AnimatedCard>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.compactRow, showDivider && styles.compactDivider]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      {/* Line 1: identity (rank slot, name, team/opponent) gets the full row
          width so names never truncate; then reason chips; then value, ring,
          bid and the chevron that opens the player. */}
      <View style={styles.compactIdentity}>{identity}</View>
      <ReasonChips player={player} />
      <View style={styles.compactMetaRow}>
        <View style={styles.scoreBlock}>
          <AppText style={styles.scoreLabel}>VALUE</AppText>
          <AppText style={styles.scoreNumberCompact}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
        </View>
        <OverallRatingBadge rating={player.overall_rating} positionRank={player.position_rank} />
        <View style={styles.compactSpacer} />
        <FAABGuidance faab={player.faab} size="compact" />
        <Ionicons name="chevron-forward" size={16} color={colors.accentSoft} />
      </View>
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    primaryCard: { padding: spacing.lg },
    actionRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.xs },
    actionLabel: {
      fontSize: 11,
      fontWeight: '700',
      color: colors.premium,
      textTransform: 'uppercase',
      letterSpacing: 0.5,
    },
    identityWrap: { marginBottom: spacing.sm },
    metricsRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.md,
      paddingTop: spacing.sm,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
    confidenceRow: { marginTop: spacing.sm, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    confidenceMeter: { flex: 1, minWidth: 0 },
    detailsButton: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      minHeight: 36,
      paddingHorizontal: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    detailsButtonText: { fontSize: 13, fontWeight: '700', color: colors.accent },
    beginnerHelp: { marginTop: spacing.xs },
    faabWhy: { marginTop: spacing.sm, fontSize: 12, lineHeight: 16, color: colors.textSecondary },
    scoreBlock: { alignItems: 'flex-start', gap: 1 },
    scoreNumberPrimary: { fontSize: 22, fontWeight: '800', color: colors.accent },
    scoreNumberCompact: { fontSize: 16, fontWeight: '700', color: colors.accent },
    scoreLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
    metricsDivider: { width: StyleSheet.hairlineWidth, alignSelf: 'stretch', backgroundColor: colors.border },
    breakdownRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'flex-end',
      gap: 2,
      marginTop: spacing.sm,
    },
    breakdownText: { fontSize: 12, fontWeight: '700', color: colors.accentSoft },
    compactRow: {
      paddingVertical: spacing.xs,
      gap: spacing.xs,
    },
    compactMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingLeft: spacing.xs },
    compactSpacer: { flex: 1 },
    compactDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    compactIdentity: { alignSelf: 'stretch' },
    // A bare chevron read as an unlabeled affordance — the concept image
    // and the redesign brief (§7: "Preserve the current Full Breakdown
    // functionality... treat it as a secondary detail action rather than a
    // giant pill") both call for this to stay visible but lightweight on
    // every priority row, not just the top target's own labeled row above.
    // Plain text + a small chevron (not a filled pill, unlike the primary
    // card's more prominent breakdownRow) keeps it a quiet, secondary
    // control per that instruction.
    //
    // Recommendation-clarity audit (product-owner ask, this pass): this was
    // previously colors.textTertiary at 10px — the same muted gray as
    // disabled/metadata text elsewhere in the app, which read as inert
    // rather than as "here is the real, working action for this
    // recommendation." Waivers has no in-app claim/add button (see
    // ScreenInfoNote below), so this chevron+label genuinely *is* the
    // action affordance for every secondary Priority Add — it needed to be
    // legible as one. Recolored to accentSoft (the same interactive-affordance
    // tone the primary card's own breakdownRow already uses) without
    // changing size/weight/shape, so it stays a quiet secondary control,
    // just no longer indistinguishable from static metadata.
  });
}
