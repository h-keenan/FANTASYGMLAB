import React from 'react';
import { StyleSheet } from 'react-native';
import Svg, { Defs, LinearGradient, RadialGradient, Rect, Stop } from 'react-native-svg';

import { colors, gradients } from '../theme';

/**
 * The app's shared screen backdrop: two layers, back to front.
 *
 * 1. A navy-to-black wash (the same `gradients.hero` pair already used on
 *    Login/Home) instead of a flat `colors.background` fill — before this,
 *    only the pre-login screens had any depth to their background and every
 *    in-league screen behind it read as flat near-black, the single biggest
 *    gap against the concept sheet's atmospheric navy-glow look.
 * 2. A soft cyan glow bloom anchored top-center, echoing the concept
 *    sheet's corner-glow treatment — kept faint on purpose (this app's
 *    established rule is distinct accents, not overdone ones).
 *
 * A hairline ops-grid pattern used to sit on top of this (ported from the
 * web app's `.stApp` rule) — removed per direct feedback on Build 32, it
 * just read as unwanted grey noise over the new navy wash rather than a
 * texture worth keeping.
 */
export default function GridBackground() {
  return (
    <Svg pointerEvents="none" style={StyleSheet.absoluteFillObject}>
      <Defs>
        <LinearGradient id="screenWash" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={gradients.hero[0]} stopOpacity={1} />
          <Stop offset="1" stopColor={gradients.hero[1]} stopOpacity={1} />
        </LinearGradient>
        <RadialGradient id="glowBloom" cx="0.5" cy="0" r="0.65">
          <Stop offset="0" stopColor={colors.accent} stopOpacity={0.12} />
          <Stop offset="1" stopColor={colors.accent} stopOpacity={0} />
        </RadialGradient>
      </Defs>
      <Rect x={0} y={0} width="100%" height="100%" fill="url(#screenWash)" />
      <Rect x={0} y={0} width="100%" height="100%" fill="url(#glowBloom)" />
    </Svg>
  );
}
