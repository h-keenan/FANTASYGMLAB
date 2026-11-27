import React from 'react';
import { StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';

/**
 * The small info icon that opens/closes a help panel: help copy lives behind it instead of in paragraphs above the field.
 * Web twin: web-next/src/components/InfoToggle.tsx.
 */
export default function InfoToggle({ open, onPress, label }: { open: boolean; onPress: () => void; label: string }) {
  const { colors } = useThemeMode();
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ expanded: open }}
      onPress={onPress}
      hitSlop={8}
      style={styles.button}
    >
      <Ionicons name={open ? 'information-circle' : 'information-circle-outline'} size={24} color={open ? colors.accent : colors.textSecondary} />
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  button: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
});
