import React, { useMemo } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import FAABGuidance from './FAABGuidance';
import PlayerIdentityRow from './PlayerIdentityRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { WaiverPriorityAdd } from '../lib/api';
import { radii, spacing, type ThemeColors } from '../theme';

const INJURY_RISK_STATUSES = new Set(['out', 'ir', 'doubtful', 'pup', 'suspended']);
const INJURY_WATCH_STATUSES = new Set(['questionable', 'sus']);

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
  if (INJURY_RISK_STATUSES.has(normalized)) return { label, tone: 'risk', ruledOut: true };
  if (INJURY_WATCH_STATUSES.has(normalized)) return { label, tone: 'watch', ruledOut: false };
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
}: {
  player: WaiverPriorityAdd;
  onPress: () => void;
  variant?: 'primary' | 'compact';
  showDivider?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = player.injury_replacement_fit ? player.injury_replacement_note : waiverOpponentContext(player);
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
        <View style={styles.metricsRow}>
          <View style={styles.scoreBlock}>
            <AppText style={styles.scoreNumberPrimary}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
            <AppText style={styles.scoreLabel}>VALUE</AppText>
          </View>
          <View style={styles.metricsDivider} />
          <FAABGuidance faab={player.faab} size="prominent" />
        </View>
        <View style={styles.breakdownRow}>
          <AppText style={styles.breakdownText}>Full breakdown</AppText>
          <Ionicons name="chevron-forward" size={14} color={colors.accentSoft} />
        </View>
      </AnimatedCard>
    );
  }

  return (
    <TouchableOpacity
      style={[styles.compactRow, showDivider && styles.compactDivider]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      <View style={styles.compactIdentity}>{identity}</View>
      <View style={styles.compactTrailing}>
        <View style={styles.compactValueRow}>
          <AppText style={styles.scoreNumberCompact}>{player.score != null ? Math.round(player.score) : '—'}</AppText>
          <RecommendationPill label={player.recommendation_label} tone={player.recommendation_tone} />
        </View>
        <FAABGuidance faab={player.faab} size="compact" />
      </View>
      <View style={styles.compactBreakdown}>
        <AppText style={styles.compactBreakdownText}>Full breakdown</AppText>
        <Ionicons name="chevron-forward" size={14} color={colors.accentSoft} />
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
    scoreBlock: { alignItems: 'flex-start', gap: 1 },
    scoreNumberPrimary: { fontSize: 22, fontWeight: '800', color: colors.accent },
    scoreNumberCompact: { fontSize: 16, fontWeight: '700', color: colors.accent },
    scoreLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.5 },
    compactValueRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
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
      flexDirection: 'row',
      alignItems: 'center',
      paddingVertical: spacing.xs,
      gap: spacing.sm,
    },
    compactDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    compactIdentity: { flex: 1 },
    compactTrailing: { alignItems: 'flex-end', gap: 2 },
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
    compactBreakdown: { flexDirection: 'row', alignItems: 'center', gap: 2, marginLeft: spacing.xs },
    compactBreakdownText: { fontSize: 10.5, fontWeight: '700', color: colors.accentSoft },
  });
}
