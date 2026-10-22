import React, { useMemo } from 'react';
import { Linking, StyleSheet, type StyleProp, type ViewStyle, View } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, typography, type ThemeColors } from '../theme';

/**
 * Small "Values informed by FantasyCalc" credit for screens that show player
 * values. Our dynasty values blend in FantasyCalc's market values
 * (modules/fantasycalc.py), and FantasyCalc's Terms of Usage
 * (https://fantasycalc.com/terms-of-usage, effective 2026-10-10) require a
 * visible "FantasyCalc" credit linking to fantasycalc.com wherever their data
 * or derivatives are shown. Same wording as web-next's ValuesCredit.tsx. Keep
 * it neutral: the terms also forbid implying a partnership or endorsement.
 */
export const FANTASYCALC_URL = 'https://fantasycalc.com';

export default function ValuesCredit({ style }: { style?: StyleProp<ViewStyle> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.wrap, style]}>
      <AppText style={styles.text}>
        Values informed by{' '}
        <AppText
          style={styles.link}
          accessibilityRole="link"
          onPress={() => void Linking.openURL(FANTASYCALC_URL)}
        >
          FantasyCalc
        </AppText>
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { paddingVertical: spacing.md },
    text: { ...typography.caption, color: colors.textTertiary, textAlign: 'center' },
    link: { ...typography.caption, color: colors.textSecondary, textDecorationLine: 'underline' },
  });
}
