import React from 'react';
import { Image, type ImageStyle, type StyleProp } from 'react-native';
import { useThemeMode } from '../context/ThemeModeContext';

/** Width / height of `assets/brand-mark.png` (trimmed FD mark, 1024x480). */
export const BRAND_MARK_ASPECT = 1024 / 480;

/**
 * The FantasyDesk "FD" brand mark, the same artwork as web-next's
 * `public/brand-mark.png` (the source of the web favicon and app icon).
 *
 * The asset is a solid-black mark on a transparent background, tinted here
 * to `colors.textPrimary`, so it reads white on the dark theme and near-black
 * on the light theme. That mirrors web's `.brand-mark-icon` rule (inverted to
 * white on the dark-first theme, black under a light scheme).
 *
 * Callers pass a bounding box; the mark is `contain`-fit inside it, so a box
 * that is not 2.13:1 just letterboxes. Pass `color` to force a fixed tint
 * (e.g. share cards that always render on a dark ground).
 */
export default function BrandMark({
  width = 160,
  height,
  color,
  style,
}: {
  width?: number;
  height?: number;
  color?: string;
  style?: StyleProp<ImageStyle>;
}) {
  const { colors } = useThemeMode();
  return (
    <Image
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      source={require('../../assets/brand-mark.png')}
      style={[{ width, height: height ?? Math.round(width / BRAND_MARK_ASPECT), tintColor: color ?? colors.textPrimary }, style]}
      resizeMode="contain"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
    />
  );
}
