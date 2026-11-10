import React from 'react';
import { Linking, StyleSheet, TouchableOpacity, type StyleProp, type ViewStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { LINK_HIT_SLOP } from '../theme';
import { HELP_LINK_LABEL, supportMailto, type SupportContext } from '../lib/support';

/**
 * The one help / feedback entry (mailto, prefilled with where the user was).
 * Mirrors web-next/src/components/HelpLink.tsx.
 */
export default function HelpLink({
  context,
  label = HELP_LINK_LABEL,
  style,
}: {
  context?: SupportContext;
  label?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  return (
    <TouchableOpacity
      accessibilityRole="link"
      accessibilityLabel={label}
      hitSlop={LINK_HIT_SLOP}
      onPress={() => void Linking.openURL(supportMailto(context)).catch(() => {})}
      style={[styles.hit, style]}
    >
      <AppText style={[styles.text, { color: colors.textTertiary }]}>{label}</AppText>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  hit: { alignSelf: 'center', paddingVertical: 6 },
  text: { fontSize: 13, textDecorationLine: 'underline' },
});
