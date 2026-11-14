import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { pickBadge, type PickBadgeInput } from '../lib/pickBadge';
import { type ThemeColors } from '../theme';

/**
 * THE draft-pick avatar (twin of web-next/src/components/PickAvatar.tsx): a round badge ("R1", pick number small
 * underneath) in the same circular slot a player photo takes. Never an illustration. Every pick render uses it.
 */
export default function PickAvatar({ size = 36, ...input }: PickBadgeInput & { size?: number }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const badge = pickBadge(input);
  const small = badge.bottom != null;
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={badge.a11y}
      testID="pick-avatar"
      style={[styles.circle, { width: size, height: size, borderRadius: size / 2, borderWidth: size >= 40 ? 3 : 2 }]}
    >
      <AppText allowFontScaling={false} style={[styles.text, { fontSize: Math.max(9, Math.round(size * (small ? 0.3 : 0.34))), lineHeight: Math.round(size * 0.36) }]}>{badge.top}</AppText>
      {small ? <AppText allowFontScaling={false} style={[styles.text, { fontSize: Math.max(7, Math.round(size * 0.22)), lineHeight: Math.round(size * 0.24), opacity: 0.8 }]}>{badge.bottom}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    circle: { alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceSolid, borderColor: colors.accent },
    text: { fontWeight: '800', color: colors.accent },
  });
}
