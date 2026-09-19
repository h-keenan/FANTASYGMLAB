import React from 'react';
import { StyleSheet, Text, type TextProps } from 'react-native';

/**
 * Drop-in replacement for RN's `Text` that renders in Inter — the brand
 * sheet (theme.ts's own header comment) specifies Inter SemiBold/Medium/
 * Regular, but almost every screen hand-rolls its own fontSize/fontWeight
 * inline rather than reading the shared `typography` tokens, so there was
 * no single place to flip to change the rendered typeface. The classic
 * "patch Text.render once" trick doesn't work on this RN version (Text is
 * built with the new Flow `component(...)` syntax, not `forwardRef`, so
 * there's no `.render` static to intercept), and React 19 no longer applies
 * function-component `defaultProps` — so every screen's `<Text>` import was
 * swapped for this one instead.
 *
 * Weight-aware rather than a single flat family: a style's own `fontWeight`
 * (the existing 700/600/500/400 hierarchy every screen already sets) maps
 * to the matching Inter static weight file, so headings/labels/body text
 * keep reading at different visual weights instead of flattening to one
 * face. An explicit `fontFamily` in the caller's own style always wins
 * (e.g. GmOrb's monospace debug text).
 */
const WEIGHT_TO_INTER_FAMILY: Record<string, string> = {
  normal: 'Inter_400Regular',
  '100': 'Inter_400Regular',
  '200': 'Inter_400Regular',
  '300': 'Inter_400Regular',
  '400': 'Inter_400Regular',
  '500': 'Inter_500Medium',
  '600': 'Inter_600SemiBold',
  bold: 'Inter_700Bold',
  '700': 'Inter_700Bold',
  '800': 'Inter_800ExtraBold',
  '900': 'Inter_800ExtraBold',
};

function interFamilyFor(style: TextProps['style']): string {
  const flat = (StyleSheet.flatten(style) ?? {}) as { fontWeight?: string | number; fontFamily?: string };
  if (flat.fontFamily) return flat.fontFamily;
  const weight = String(flat.fontWeight ?? '400');
  return WEIGHT_TO_INTER_FAMILY[weight] ?? 'Inter_400Regular';
}

export default function AppText({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[{ fontFamily: interFamilyFor(style) }, style]} />;
}
