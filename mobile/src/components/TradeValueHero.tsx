import React from 'react';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors } from '../theme';

type HeroSize = 'sm' | 'lg';

const SIZES: Record<HeroSize, { value: number; label: number; tracking: number }> = {
  // Feed density: Trade Hub stacks many of these, so `sm` is deliberately
  // smaller than the share PNG's 40pt hero while still reading as the
  // card's headline number rather than a metadata chip.
  sm: { value: 26, label: 9, tracking: -0.6 },
  lg: { value: 40, label: 12, tracking: -1 },
};

/** Same green/red/neutral mapping TradeShareCard uses for its hero number,
 * so the inline treatment and the shared PNG agree on what a gain looks like. */
export function tradeValueColor(delta: number): string {
  return delta > 0 ? colors.successBright : delta < 0 ? colors.danger : colors.textSecondary;
}

export function tradeValueLabel(delta: number): string {
  return `${delta > 0 ? '+' : ''}${delta.toLocaleString()}`;
}

/**
 * The big, color-coded value-change number from the share card
 * (TradeShareCard's `gainValue`/`gainLabel`), extracted so the *inline*
 * surfaces — Trade Analyzer's verdict and Trade Hub's idea feed — can lead
 * with it instead of leaving it behind the Share button. Deliberately just
 * the number + caption: the share card's QR, brand header and tagline
 * footer only make sense on a fixed-size exported graphic.
 */
export default function TradeValueHero({
  delta,
  size = 'lg',
  label = 'Value Change',
  style,
}: {
  delta: number;
  size?: HeroSize;
  label?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const metrics = SIZES[size];
  const tone = tradeValueColor(delta);
  const value = tradeValueLabel(delta);

  return (
    <View style={style} accessible accessibilityLabel={`${label}: ${value}`}>
      <Text
        style={[styles.value, { color: tone, fontSize: metrics.value, letterSpacing: metrics.tracking }]}
        numberOfLines={1}
        adjustsFontSizeToFit
      >
        {value}
      </Text>
      <Text style={[styles.label, { fontSize: metrics.label }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  value: { fontWeight: '800' },
  label: { color: colors.textSecondary, marginTop: -2 },
});
