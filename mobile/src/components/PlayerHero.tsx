import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import OvrGauge from './OvrGauge';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import TapForWhy from './TapForWhy';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { UsageTrend } from '../lib/api';
import { byePills } from '../lib/playerByePresentation';
import { heroInitials } from '../lib/playerQuickViewPresentation';
import { byePillText } from '../lib/playerAvailability';
import { sentenceCase, usageConfidenceBars, usageTrendTone } from '../lib/usageTrendPresentation';
import { radii, spacing, type ThemeColors } from '../theme';
import PlayerName from './PlayerName';

/**
 * Player Detail's identity header, rebuilt from the owner's Player Quick
 * View concept (2026-10-21) so it matches web's PQV header
 * (web-next PlayerHeroHeader):
 * - headshot with a soft accent glow, and the archetype (tier) as a
 *   rounded pill with an icon under it, bordered in the tier's color;
 * - a larger name, with the position badge and a bordered "TEAM • Age N"
 *   pill beside it;
 * - three equal tiles: the player score ring (still the tap target that
 *   expands the Snapshot card below, per coridian_'s "tap the overall for
 *   the expanded information"), value, and the usage trend with its
 *   confidence inside the tile, colored by direction and severity.
 *
 * Missing data keeps its tile with a dash; while the quick-view read is
 * loading, the usage tile shows a placeholder rather than "no trend".
 * Tags, actions, roster recommendation and news still render below as
 * `children`.
 */
export default function PlayerHero({
  playerId,
  avatarId,
  tier,
  tierLabel,
  tierColor,
  name,
  position,
  team,
  age,
  score,
  overallRating,
  ringColor,
  usageTrend,
  usageLoading = false,
  valueNote,
  valueLabel,
  byeWeek = null,
  onByeThisWeek = false,
  unavailable = false,
  rookie = null,
  expanded,
  onToggleExpand,
  valueChart = null,
  ovrChart = null,
  children,
}: {
  /** Shown in the tap-the-Value popover (for example the value history chart). */
  valueChart?: React.ReactNode;
  /** Shown in the tap-the-Player-score popover (for example the model radar). */
  ovrChart?: React.ReactNode;
  playerId: string;
  /** Photo id when it differs from playerId; null = no photo exists (initials). */
  avatarId?: string | null;
  tier?: string | null;
  /** Archetype pill text (resolvePlayerTier's semantic label); omit for
   * no tier. */
  tierLabel?: string | null;
  tierColor: string;
  name: string;
  position?: string | null;
  team?: string | null;
  age?: number | null;
  score?: number | null;
  /** 0-99 headline rating, null when the position pool is too thin to rank
   * against: the tile shows a dash, never a fabricated value. */
  overallRating: number | null;
  ringColor: string;
  usageTrend: UsageTrend | null;
  usageLoading?: boolean;
  /** Server-provided reason the Value tile is empty (e.g. "No market value yet"). */
  valueNote?: string | null;
  /** Overrides the VALUE caption (and explainer) when the number is not the real market value: Fantasy Sim passes "Trade value". */
  valueLabel?: string | null;
  /** Team bye week (null when unknown / free agent). */
  byeWeek?: number | null;
  /** True when the current NFL week is that bye. */
  onByeThisWeek?: boolean;
  /** Out/IR/doubtful: the bye stays secondary (pill only). */
  unavailable?: boolean;
  /** ROOKIE badge from rookieBadge(bio); null for everyone else. */
  rookie?: { label: string; detail: string | null } | null;
  /** Whether the caller's Snapshot detail is currently shown. */
  expanded?: boolean;
  /** Supplying this turns the score tile into the expand toggle for the
   * Snapshot card; omit to keep it static. */
  onToggleExpand?: () => void;
  children?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const bye = byePills(byeWeek, onByeThisWeek);

  const scoreTileBody = (
    <>
      {overallRating !== null ? (
        <OvrGauge rating={overallRating} size="md" color={ringColor} />
      ) : (
        <AppText style={[styles.tileValue, styles.tileValueEmpty]}>—</AppText>
      )}
      <View style={styles.captionRow}>
        <AppText style={styles.tileCaption}>PLAYER SCORE</AppText>
        {onToggleExpand && overallRating !== null ? (
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={10} color={colors.textTertiary} />
        ) : null}
      </View>
    </>
  );

  return (
    <View style={styles.wrap}>
      <View style={styles.identityRow}>
        <View style={styles.avatarCol}>
          <View style={[styles.avatarGlow, { shadowColor: colors.accent, borderColor: colors.accentMuted }]}>
            <PlayerAvatar playerId={avatarId === undefined ? playerId : avatarId} size={100} tier={tier} fallbackLabel={heroInitials(name)} />
          </View>
          {tierLabel ? (
            <View style={[styles.archetypePill, { borderColor: tierColor }]}>
              <Ionicons name="person" size={11} color={tierColor} />
              <AppText style={styles.archetypeText} numberOfLines={1}>
                {tierLabel}
              </AppText>
            </View>
          ) : null}
        </View>
        <View style={styles.infoCol}>
          <PlayerName name={name} style={styles.name} />
          <View style={styles.metaRow}>
            <PositionBadge position={position} size="md" />
            <View style={styles.metaPill}>
              <AppText style={styles.metaPillText}>{team || (usageLoading ? '—' : 'FA')}</AppText>
              <AppText style={styles.metaPillDot}>•</AppText>
              <AppText style={styles.metaPillText}>Age {age ?? (usageLoading ? '—' : 'N/A')}</AppText>
            </View>
            {rookie ? <ToneBadge label={rookie.label} color={colors.accent} /> : null}
            {bye.label ? (
              <View style={styles.metaPill} testID="pqv-bye-pill">
                <AppText style={styles.metaPillText}>{byeWeek != null ? byePillText(byeWeek, onByeThisWeek === true, unavailable) : bye.label}</AppText>
              </View>
            ) : null}
            {bye.thisWeek && !unavailable ? <ToneBadge label="On bye this week" color={colors.premium} /> : null}
          </View>
          {rookie?.detail ? <AppText style={styles.rookieLine}>Rookie · {rookie.detail}</AppText> : null}
        </View>
      </View>

      <View style={styles.tilesRow}>
        {onToggleExpand && overallRating !== null ? (
          <PressableScale
            style={styles.tile}
            onPress={onToggleExpand}
            accessibilityRole="button"
            accessibilityLabel={`Player score ${overallRating}. ${expanded ? 'Hide' : 'Show'} value snapshot`}
          >
            {scoreTileBody}
          </PressableScale>
        ) : overallRating !== null ? (
          <TapForWhy metric="ovr" variant="tile" style={styles.tile} spoken={`Player score ${overallRating}`} chart={ovrChart} testID="pqv-ovr-why">
            {scoreTileBody}
          </TapForWhy>
        ) : (
          <View style={styles.tile}>{scoreTileBody}</View>
        )}
        {score != null ? (
          <TapForWhy metric={valueLabel ? 'trade_value' : 'value'} variant="tile" style={styles.tile} spoken={`${valueLabel ?? 'Value'} ${Math.round(score).toLocaleString()}`} chart={valueChart} testID="pqv-value-why">
            <AppText style={styles.tileCaption}>{(valueLabel ?? 'Value').toUpperCase()}</AppText>
            <AppText style={styles.tileValue} numberOfLines={1} adjustsFontSizeToFit>
              {Math.round(score).toLocaleString()}
            </AppText>
          </TapForWhy>
        ) : (
          usageLoading ? (
            <View style={styles.tile}>
              <AppText style={styles.tileCaption}>{(valueLabel ?? 'Value').toUpperCase()}</AppText>
              <AppText style={[styles.tileValue, styles.tileValueEmpty]}>—</AppText>
            </View>
          ) : (
            <TapForWhy
              metric={valueLabel ? 'trade_value' : 'value'}
              variant="tile"
              style={styles.tile}
              spoken="Value, none yet"
              title="Why there is no value"
              extra={[valueNote || 'No market value yet', 'A player gets a value once the market prices him. Until then the tile stays empty rather than showing a made-up number.']}
              testID="pqv-value-empty"
            >
              <AppText style={styles.tileCaption}>{(valueLabel ?? 'Value').toUpperCase()}</AppText>
              <AppText style={[styles.tileValue, styles.tileValueEmpty]}>—</AppText>
              <AppText style={styles.tileNote}>{valueNote || 'No market value yet'}</AppText>
            </TapForWhy>
          )
        )}
        <UsageTile trend={usageTrend} loading={usageLoading} />
      </View>
      {children}
    </View>
  );
}

function UsageTile({ trend, loading }: { trend: UsageTrend | null; loading: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!trend) {
    return (
      <View style={styles.tile}>
        <AppText style={[styles.tileValue, styles.tileValueEmpty]}>{loading ? '…' : '—'}</AppText>
        <AppText style={styles.tileCaption}>USAGE</AppText>
        {loading ? null : <AppText style={styles.tileNote}>No clear trend</AppText>}
      </View>
    );
  }
  const tone = usageTrendTone(trend);
  const tint = tone === 'positive' ? colors.success : tone === 'danger' ? colors.danger : colors.textSecondary;
  const background = tone === 'positive' ? colors.successMuted : tone === 'danger' ? colors.dangerMuted : undefined;
  const magnitude = Math.abs(trend.trend_pct);
  const confidence = sentenceCase(trend.confidence_label);
  const lit = usageConfidenceBars(trend.confidence_label);
  return (
    <TapForWhy
      metric="usage_trend"
      variant="tile"
      style={[styles.tile, tone !== 'neutral' && { borderColor: tint, backgroundColor: background }]}
      spoken={`Usage ${trend.direction === 'up' ? 'up' : 'down'} ${magnitude}%, ${confidence.toLowerCase()}`}
      extra={trend.detail ? [trend.detail] : undefined}
      testID="pqv-usage-why"
    >
      <AppText style={[styles.tileValue, { color: tint }]} numberOfLines={1} adjustsFontSizeToFit>
        {trend.arrow} {magnitude}%
      </AppText>
      <AppText style={styles.tileCaption}>USAGE</AppText>
      <View style={[styles.tileDivider, { backgroundColor: tone === 'neutral' ? colors.border : tint }]} />
      <View style={styles.confidenceRow}>
        <View style={styles.signalBars}>
          {[0, 1, 2].map((index) => (
            <View
              key={index}
              style={[
                styles.signalBar,
                { height: 4 + index * 3, backgroundColor: tint, opacity: index < lit ? 1 : 0.3 },
              ]}
            />
          ))}
        </View>
        <AppText style={[styles.confidenceText, { color: tint }]} numberOfLines={2}>
          {confidence}
        </AppText>
      </View>
    </TapForWhy>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { marginBottom: spacing.lg, gap: spacing.md },
    identityRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.lg },
    avatarCol: { alignItems: 'center', gap: spacing.sm },
    // Soft accent glow around the headshot (concept); the tier prestige
    // ring itself stays PlayerAvatar's.
    avatarGlow: {
      borderRadius: 999,
      borderWidth: 1,
      shadowOpacity: 0.45,
      shadowRadius: 14,
      shadowOffset: { width: 0, height: 0 },
      elevation: 6,
    },
    archetypePill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.xs,
      maxWidth: 124,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.xs,
      borderRadius: radii.pill,
      borderWidth: 1,
      backgroundColor: colors.backgroundElevated,
    },
    archetypeText: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    infoCol: { flex: 1, alignItems: 'flex-start', gap: spacing.sm, paddingTop: spacing.xs },
    name: { fontSize: 29, fontWeight: '800', color: colors.textPrimary, lineHeight: 32, letterSpacing: -0.3 },
    rookieLine: { fontSize: 13.5, color: colors.textSecondary },
    metaRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    metaPill: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: 2,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
    },
    metaPillText: { fontSize: 15, fontWeight: '600', color: colors.textSecondary },
    metaPillDot: { fontSize: 12, color: colors.textTertiary },
    tilesRow: { flexDirection: 'row', gap: spacing.sm },
    tile: {
      flex: 1,
      minHeight: 96,
      alignItems: 'center',
      justifyContent: 'center',
      gap: spacing.xs,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.xs,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.backgroundElevated,
    },
    tileValue: { fontSize: 23, fontWeight: '800', color: colors.textPrimary },
    tileValueEmpty: { color: colors.textTertiary },
    captionRow: { flexDirection: 'row', alignItems: 'center', gap: 2 },
    tileCaption: { fontSize: 12, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary },
    tileNote: { fontSize: 12, color: colors.textTertiary },
    tileDivider: { alignSelf: 'stretch', height: StyleSheet.hairlineWidth, marginHorizontal: spacing.sm, opacity: 0.6 },
    confidenceRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingHorizontal: 2 },
    signalBars: { flexDirection: 'row', alignItems: 'flex-end', gap: 2 },
    signalBar: { width: 3, borderRadius: 1 },
    confidenceText: { flexShrink: 1, fontSize: 12, fontWeight: '700', lineHeight: 14 },
  });
}
