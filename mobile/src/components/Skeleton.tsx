import React, { useMemo } from 'react';
import { StyleSheet, View, type DimensionValue, type StyleProp, type ViewStyle } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { useAnimatedStyle, useSharedValue } from 'react-native-reanimated';

import { radii, spacing, type ThemeColors } from '../theme';
import { useThemeMode } from '../context/ThemeModeContext';
import { useShimmerClock } from '../lib/shimmerClock';
import { pageTabFamily, type PageTabFamilyKey } from '../lib/pageFamilies';
import SlowLoadNote from './SlowLoadNote';
import { avatarSize, type AvatarTier } from '../lib/playerAnatomy';

/**
 * THE shared skeleton set (twin of web-next/src/components/Skeleton.tsx; docs/ui-patterns.md, "Loading identity"):
 * block, avatar circle, header, hero, tab strip, module, player row, trade card, status header, whole page. Every
 * loading state in the app is composed from these so the placeholder keeps the silhouette of the content that is
 * about to appear (and the page does not jump when it lands). The shared templates (CompactModule,
 * PlayerAccordionRow, TradeCompactCard, StatusHeader) draw them for their own loading state. This file is the only
 * place allowed to draw a loading placeholder (skeletonScan.test.ts bans a bare `ActivityIndicator` screen or a
 * "Loading..." line anywhere else). One shared shimmer clock drives every sweep; it freezes under Reduce Motion and the Reduced effects setting.
 */
export function SkeletonBlock({
  width = '100%',
  height = 16,
  radius = radii.sm,
  style,
}: {
  width?: DimensionValue;
  height?: number;
  radius?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors, isDark } = useThemeMode();
  const { clock, running } = useShimmerClock();
  const w = useSharedValue(0);

  // One diagonal glass sweep (translateX of a gradient band) driven by the ONE shared clock; frozen when not running.
  const sweepStyle = useAnimatedStyle(() => ({
    opacity: running ? 1 : 0,
    transform: [{ translateX: -w.value * 0.6 + clock.value * w.value * 1.6 }, { skewX: '-18deg' }],
  }));

  return (
    <View
      onLayout={(e) => {
        w.value = e.nativeEvent.layout.width;
      }}
      style={[
        {
          width,
          height,
          borderRadius: radius,
          backgroundColor: colors.backgroundElevated,
          overflow: 'hidden',
        },
        style,
      ]}
    >
      <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFillObject, { width: '60%' }, sweepStyle]}>
        <LinearGradient
          colors={['rgba(255,255,255,0)', isDark ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.65)', 'rgba(255,255,255,0)']}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={StyleSheet.absoluteFillObject}
        />
      </Animated.View>
    </View>
  );
}

/**
 * Card-shaped placeholder matching `AnalyticsSection`'s own card chrome
 * (surface fill, cardBorder hairline, `radii.md`, header row) so a loading
 * analytics group reads as "a card like this is coming" rather than a void.
 * `rows` controls how many metric-tile-shaped blocks render inside — pass
 * an even number to roughly match a 2-column `MetricCard` grid.
 */
export function SkeletonCard({
  rows = 4,
  style,
}: {
  /** Number of metric-tile-shaped blocks inside the card (MetricCard's grid
   * is 2-up, so pairs look most like the real thing). */
  rows?: number;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.card, style]}>
      <View style={styles.cardHeaderRow}>
        <SkeletonBlock width={16} height={16} radius={radii.sm} />
        <SkeletonBlock width={100} height={13} style={styles.cardHeaderTitle} />
      </View>
      <View style={styles.cardGrid}>
        {Array.from({ length: rows }, (_, index) => (
          <SkeletonBlock key={index} width="46%" height={62} radius={radii.sm} style={styles.cardTile} />
        ))}
      </View>
    </View>
  );
}

/** Row-shaped placeholder for a single list item — a player row, a trade
 * card, a waiver recommendation — sized for a portrait/avatar-left,
 * two-line-text-right layout, the shape nearly every list row in the app
 * shares. Colorless by design (its children, `SkeletonBlock`s, carry the
 * only themed fill) so it needs no theme lookup of its own. */
export function SkeletonRow({ style }: { style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[rowStyles.row, style]}>
      <SkeletonBlock width={40} height={40} radius={radii.pill} />
      <View style={rowStyles.rowTextGroup}>
        <SkeletonBlock width="70%" height={14} />
        <SkeletonBlock width="45%" height={11} />
      </View>
    </View>
  );
}

/** A stack of `SkeletonRow`s for a list that is still loading. */
export function SkeletonRows({ count = 5, style }: { count?: number; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={style}>
      {Array.from({ length: count }, (_, index) => (
        <SkeletonRow key={index} />
      ))}
    </View>
  );
}

const rowStyles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm },
  playerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 44, paddingVertical: 2 },
  rowTextGroup: { flex: 1, gap: spacing.xs },
  headerGroup: { gap: spacing.sm },
  tabs: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: 6, minHeight: 44, borderRadius: radii.pill },
  hero: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, padding: spacing.lg },
  module: { padding: spacing.md, gap: spacing.xs, minHeight: 44 },
  statRow: { flexDirection: 'row', gap: spacing.sm },
});

/** Chart-shaped placeholder sized to `WeeklyPointsChart`'s own fixed
 * `HEIGHT` (140) so the points-by-week section doesn't jump when the real
 * chart mounts — a flat shimmering plot area reads closer to "a chart is
 * loading here" than a spinner centered in the same space. */
export function SkeletonChart({ style }: { style?: StyleProp<ViewStyle> }) {
  return <SkeletonBlock height={140} radius={radii.sm} style={style} />;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: {
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.md,
      marginTop: spacing.sm,
    },
    cardHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    cardHeaderTitle: {},
    cardGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    cardTile: { minWidth: 64, flexGrow: 1 },
  });
}

export default SkeletonBlock;

const glassCard = (colors: ThemeColors) => ({
  backgroundColor: colors.surface,
  borderRadius: radii.md,
  borderWidth: StyleSheet.hairlineWidth * 1.5,
  borderColor: colors.cardBorder,
});

/** The round placeholder where a player (or team) avatar will be. Sizes follow the avatar density tiers. */
export function SkeletonAvatar({ tier = 'row', size }: { tier?: AvatarTier; size?: number }) {
  const px = size ?? avatarSize(tier);
  return <SkeletonBlock width={px} height={px} radius={radii.pill} style={{ flexShrink: 0 }} />;
}

/** A PlayerAccordionRow silhouette: avatar, name + meta lines, one trailing number. Same 44pt minimum as the real row. */
export function SkeletonPlayerRow({ tier = 'row', trailing = true, style }: { tier?: AvatarTier; trailing?: boolean; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[rowStyles.playerRow, style]} testID="skeleton-player-row">
      <SkeletonAvatar tier={tier} />
      <View style={rowStyles.rowTextGroup}>
        <SkeletonBlock width="55%" height={14} />
        <SkeletonBlock width="38%" height={11} />
      </View>
      {trailing ? <SkeletonBlock width={34} height={26} /> : null}
    </View>
  );
}

/** A stack of player rows. */
export function SkeletonPlayerRows({ count = 4, tier = 'row' }: { count?: number; tier?: AvatarTier }) {
  return (
    <View>
      {Array.from({ length: count }, (_, index) => (
        <SkeletonPlayerRow key={index} tier={tier} />
      ))}
    </View>
  );
}

/** A page title + one muted subtitle line. */
export function SkeletonHeader({ subtitle = true }: { subtitle?: boolean }) {
  return (
    <View style={rowStyles.headerGroup} testID="skeleton-header">
      <SkeletonBlock width="52%" height={26} />
      {subtitle ? <SkeletonBlock width="34%" height={12} /> : null}
    </View>
  );
}

/** The page-family tab strip (SegmentedTabBar): `count` pills in a glass bar. */
export function SkeletonTabs({ count = 4 }: { count?: number }) {
  const { colors } = useThemeMode();
  return (
    <View style={[glassCard(colors), rowStyles.tabs]} testID="skeleton-tabs">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonBlock key={index} height={32} radius={radii.pill} style={{ flex: 1 }} />
      ))}
    </View>
  );
}

/** The hero zone (Today / team status / player hero): avatar-or-ring, kicker, headline, supporting line in one card. */
export function SkeletonHero({ minHeight = 150 }: { minHeight?: number }) {
  const { colors } = useThemeMode();
  return (
    <View style={[glassCard(colors), rowStyles.hero, { minHeight }]} testID="skeleton-hero">
      <SkeletonAvatar size={54} />
      <View style={rowStyles.rowTextGroup}>
        <SkeletonBlock width="30%" height={10} />
        <SkeletonBlock width="80%" height={18} />
        <SkeletonBlock width="60%" height={13} />
      </View>
    </View>
  );
}

/** A CompactModule silhouette: title line, one or two summary lines. */
export function SkeletonModule({ lines = 2, style }: { lines?: number; style?: StyleProp<ViewStyle> }) {
  const { colors } = useThemeMode();
  return (
    <View style={[glassCard(colors), rowStyles.module, style]} testID="skeleton-module">
      <SkeletonBlock width="28%" height={10} />
      {Array.from({ length: Math.max(1, Math.min(2, lines)) }, (_, index) => (
        <SkeletonBlock key={index} width={index === 0 ? '88%' : '58%'} height={13} />
      ))}
    </View>
  );
}

/** A TradeCompactCard silhouette: title, give and get sides of avatar rows, the fairness meter. */
export function SkeletonTradeCard({ assets = 2 }: { assets?: number }) {
  const { colors } = useThemeMode();
  return (
    <View style={[glassCard(colors), rowStyles.module, { gap: spacing.sm }]} testID="skeleton-trade-card">
      <SkeletonBlock width="46%" height={14} />
      {[0, 1].map((side) => (
        <View key={side}>
          <SkeletonBlock width="24%" height={10} />
          {Array.from({ length: side === 0 ? assets : Math.max(1, assets - 1) }, (_, index) => (
            <SkeletonPlayerRow key={index} tier="card" trailing={false} />
          ))}
        </View>
      ))}
      <SkeletonBlock height={8} radius={radii.pill} />
    </View>
  );
}

/** A StatusHeader silhouette: ring + headline, three mini stats, player rows, the primary button. */
export function SkeletonStatusHeader({ rows = 3 }: { rows?: number }) {
  const { colors } = useThemeMode();
  return (
    <View style={[glassCard(colors), rowStyles.module, { gap: spacing.md }]} testID="skeleton-status-header">
      <View style={rowStyles.hero}>
        <SkeletonAvatar size={54} />
        <View style={rowStyles.rowTextGroup}>
          <SkeletonBlock width="30%" height={10} />
          <SkeletonBlock width="78%" height={16} />
          <SkeletonBlock width="55%" height={12} />
        </View>
      </View>
      <View style={rowStyles.statRow}>
        {[0, 1, 2].map((index) => (
          <SkeletonBlock key={index} height={46} radius={radii.sm} style={{ flex: 1 }} />
        ))}
      </View>
      <SkeletonPlayerRows count={rows} />
      <SkeletonBlock height={44} radius={radii.md} />
    </View>
  );
}

/** One named loading region: the single screen-reader name ("Loading Players"). */
export function SkeletonRegion({ label, children, style, onRetry }: { label: string; children: React.ReactNode; style?: StyleProp<ViewStyle>; onRetry?: () => void }) {
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={`Loading ${label}`} accessibilityState={{ busy: true }} style={style}>
      {children}
      <SlowLoadNote onRetry={onRetry} />
    </View>
  );
}

/** Inline text-line placeholder for a small region that is still loading. */
export function SkeletonText({ lines = 3, label, style }: { lines?: number; label: string; style?: StyleProp<ViewStyle> }) {
  return (
    <SkeletonRegion label={label} style={[{ gap: spacing.sm }, style]}>
      {Array.from({ length: lines }, (_, index) => (
        <SkeletonBlock key={index} width={index === lines - 1 ? '55%' : index === 0 ? '92%' : '78%'} height={13} />
      ))}
    </SkeletonRegion>
  );
}

/** Player-row skeleton with its own status name: the loading body of a list region. */
export function SkeletonList({ label, count = 4, tier = 'row', style }: { label: string; count?: number; tier?: AvatarTier; style?: StyleProp<ViewStyle> }) {
  return (
    <SkeletonRegion label={label} style={style}>
      <SkeletonPlayerRows count={count} tier={tier} />
    </SkeletonRegion>
  );
}

export type SkeletonLayout = 'dashboard' | 'list' | 'detail' | 'cards';

/**
 * A whole screen, content-shaped: header, optional family tab strip, then the body for the screen's family (see the
 * web twin for the layout meanings). What every route shows while auth or its first fetch resolves (LoadingScreen and
 * the per-screen loading states), instead of a spinner. `topInset` clears the navigation header.
 */
export function SkeletonPage({ label, layout = 'dashboard', family, topInset = 0, style, onRetry }: { label: string; layout?: SkeletonLayout; family?: PageTabFamilyKey; topInset?: number; style?: StyleProp<ViewStyle>; onRetry?: () => void }) {
  const tabs = family ? pageTabFamily(family).tabs.length : 0;
  const { colors } = useThemeMode();
  return (
    <SkeletonRegion label={label} onRetry={onRetry} style={[{ flex: 1, paddingHorizontal: spacing.lg, paddingTop: topInset + spacing.md, gap: spacing.lg }, style]}>
      <SkeletonHeader />
      {tabs > 0 ? <SkeletonTabs count={tabs} /> : null}
      {layout === 'dashboard' ? (
        <>
          <SkeletonStatusHeader />
          <SkeletonModule />
          <SkeletonModule />
        </>
      ) : null}
      {layout === 'list' ? (
        <>
          <SkeletonBlock height={44} radius={radii.md} />
          <View style={[glassCard(colors), { padding: spacing.sm }]}>
            <SkeletonPlayerRows count={7} />
          </View>
        </>
      ) : null}
      {layout === 'cards' ? (
        <>
          <SkeletonTradeCard />
          <SkeletonTradeCard />
        </>
      ) : null}
      {layout === 'detail' ? (
        <>
          <SkeletonHero />
          <SkeletonModule />
          <SkeletonModule />
        </>
      ) : null}
    </SkeletonRegion>
  );
}
