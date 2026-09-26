import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, type ThemeColors } from '../theme';
import { tradeValueColor, tradeValueLabel } from './TradeValueHero';

// Trade Hub's `trade_gain` (see tests/fixtures/trade_hub_golden.json)
// typically runs from the tens up into the low thousands, with most ideas
// landing between ~50 and ~1400. This constant sizes the saturating curve
// below so a modest edge (a couple hundred points) still reads as a clearly
// visible lean, while a genuine blowout keeps growing instead of hard-
// clipping at some arbitrary cutoff. It's a display-only scale for how much
// of the track to fill — it never changes the sign/color the bar (or the
// number next to it) shows, only the fill proportion.
const EDGE_SATURATION_SCALE = 900;

/**
 * Fraction (0-1) of *one side* of the center-anchored track a value edge of
 * this magnitude should fill. Saturates toward 1 for very lopsided trades
 * instead of clipping hard, and is exactly 0 for an even trade.
 */
function edgeFraction(delta: number, scale: number = EDGE_SATURATION_SCALE): number {
  const magnitude = Math.abs(delta);
  if (!Number.isFinite(magnitude) || magnitude <= 0) return 0;
  return magnitude / (magnitude + scale);
}

/**
 * Screen-reader wording for the same conclusion the bar's fill direction
 * communicates visually — a signed delta plus which side currently has the
 * edge. Mirrors TradeValueHero's own `${label}: ${value}` shape so the two
 * read as one continuous sentence to VoiceOver/TalkBack, not two
 * disconnected announcements.
 */
export function tradeValueBarAccessibilityLabel(delta: number, label = 'Value edge'): string {
  const value = tradeValueLabel(delta);
  if (delta > 0) return `${label}: ${value}. You have the edge in this trade.`;
  if (delta < 0) return `${label}: ${value}. Your opponent has the edge in this trade.`;
  return `${label}: even. Neither side has a clear value edge.`;
}

/**
 * Compact horizontal "who's winning" bar for a trade's value change — the
 * shape-based reinforcement of the color-coded delta number TradeValueHero
 * already renders (UI_HIERARCHY_DIRECTIVE.md's "pair color with shape"
 * guidance), so a card communicates the value lean at a glance instead of
 * requiring the viewer to read and sign-interpret a number.
 *
 * Diverges from a center zero point: a positive delta (favorable to the
 * user) fills rightward, a negative delta fills leftward, both tinted with
 * the exact same `tradeValueColor` mapping the number uses, so the bar and
 * the number can never disagree.
 *
 * Deliberately driven by the single net `delta` (Trade Hub's `trade_gain`,
 * Trade Analyzer/share's `value_delta`) rather than resummed per-side asset
 * totals: Trade Hub's `package.send`/`package.receive` are truncated to 3
 * assets per side before they ever reach the client
 * (modules/compact_fantasy_assets.py's `compact_package`), so resumming
 * their `score` fields here would silently misrepresent any trade with
 * more than 3 assets on a side. The net delta is the one number every
 * trade-value surface already has in full and already agrees on.
 */
export default function TradeValueBar({
  delta,
  style,
  accessibilityLabel,
  colors: colorsOverride,
}: {
  delta: number;
  style?: StyleProp<ViewStyle>;
  accessibilityLabel?: string;
  /**
   * Explicit palette override for callers outside the live theme tree —
   * TradeShareCard renders a fixed-look exported PNG from the static dark
   * `colors` import regardless of the viewer's light/dark setting, so it
   * passes that same static object here instead of picking up whatever
   * theme mode happens to be active when the card is captured.
   */
  colors?: ThemeColors;
}) {
  const { colors: themeColors } = useThemeMode();
  const colors = colorsOverride ?? themeColors;
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tone = tradeValueColor(delta, colors);
  const fraction = edgeFraction(delta);
  const label = accessibilityLabel ?? tradeValueBarAccessibilityLabel(delta);

  return (
    <View style={style} accessible accessibilityLabel={label}>
      <View style={styles.track}>
        <View style={styles.centerTick} />
        {fraction > 0 ? (
          <View
            style={[
              styles.fill,
              { backgroundColor: tone, width: `${fraction * 50}%` },
              delta > 0 ? { left: '50%' } : { right: '50%' },
            ]}
          />
        ) : null}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    track: {
      height: 6,
      borderRadius: radii.pill,
      backgroundColor: colors.backgroundElevated,
      overflow: 'hidden',
      position: 'relative',
    },
    fill: {
      position: 'absolute',
      top: 0,
      bottom: 0,
      borderRadius: radii.pill,
    },
    centerTick: {
      position: 'absolute',
      left: '50%',
      marginLeft: -1,
      top: -1,
      bottom: -1,
      width: 2,
      backgroundColor: colors.hairline,
    },
  });
}
