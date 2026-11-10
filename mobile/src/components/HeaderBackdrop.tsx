import React from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';

import { useThemeMode } from '../context/ThemeModeContext';

/**
 * Backdrop for the transparent native-stack header (RootNavigator sets
 * `headerTransparent` so the screen gradient can bleed up to the top).
 * Without a backdrop, scrolling rows ran visibly through the title and the
 * league/sort/lens chips ("Dashboard" drawn over player rows). A blur plus a
 * mostly-opaque background wash fully covers the status bar + header area,
 * then fades out at the bottom edge so there is no hard seam. The header's
 * own height (status bar inset included) sizes this view, so safe-area
 * handling is inherited.
 */
export default function HeaderBackdrop() {
  const { colors, isDark } = useThemeMode();
  const solid = colors.background;
  const clear = isDark ? 'rgba(0,0,0,0)' : 'rgba(217,227,234,0)';
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
      {Platform.OS === 'ios' ? (
        <BlurView intensity={40} tint={isDark ? 'dark' : 'light'} style={StyleSheet.absoluteFill} />
      ) : null}
      <LinearGradient colors={[solid, solid, clear]} locations={[0, 0.82, 1]} style={StyleSheet.absoluteFill} />
    </View>
  );
}
