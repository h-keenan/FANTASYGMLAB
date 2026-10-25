import React, { useMemo } from 'react';
import { StyleSheet, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import type { ThemeColors } from '../theme';

/**
 * The one screen title (web `--font-page-title` h1): 22/800, tight tracking.
 * Used by the Dashboard header bar and Matchup so page titles stop varying
 * per screen (Matchup was 26, Dashboard 22).
 */
export default function PageTitle({ children, style }: { children: React.ReactNode; style?: StyleProp<TextStyle> }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <AppText style={[styles.title, style]} accessibilityRole="header">
      {children}
    </AppText>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    title: { fontSize: 22, fontWeight: '800', letterSpacing: -0.2, color: colors.textPrimary },
  });
}
