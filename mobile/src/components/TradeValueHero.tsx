import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

type HeroSize = 'sm' | 'md' | 'lg';

const SIZES: Record<HeroSize, { value: number; label: number; tracking: number }> = {
  // Feed density: Trade Hub stacks many of these, so `sm` is deliberately
  // smaller than the share PNG's 40pt hero while still reading as the
  // card's headline number rather than a metadata chip.
  sm: { value: 26, label: 9, tracking: -0.6 },
  // Trade Hub's concept mockups (not available when `sm` above was chosen)
  // show the value-change number as the clear focal point of the card —
  // closer to the share PNG's 40pt hero than the original 26pt feed size.
  // `md` splits the difference: still a step down from `lg` so a dense feed
  // of cards doesn't balloon in height, but sized so the number reads as
  // "the strongest visual element" the way the concept renders it.
  md: { value: 34, label: 10, tracking: -0.8 },
  lg: { value: 40, label: 12, tracking: -1 },
};

/** Same green/red/neutral mapping TradeShareCard uses for its hero number,
 * so the inline treatment and the shared PNG agree on what a gain looks like. */
export function tradeValueColor(delta: number, colors: ThemeColors): string {
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const metrics = SIZES[size];
  const tone = tradeValueColor(delta, colors);
  const value = tradeValueLabel(delta);

  return (
    <View style={style} accessible accessibilityLabel={`${label}: ${value}`}>
      <AppText
        style={[styles.value, { color: tone, fontSize: metrics.value, letterSpacing: metrics.tracking }]}
        numberOfLines={1}
        adjustsFontSizeToFit
      >
        {value}
      </AppText>
      <AppText style={[styles.label, { fontSize: metrics.label }]}>{label}</AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    value: { fontWeight: '800' },
    label: { color: colors.textSecondary, marginTop: -2 },
  });
}
