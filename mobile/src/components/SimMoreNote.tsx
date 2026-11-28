import React, { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';

/**
 * A helper paragraph condensed to ONE line with tap-for-more: the whole line is the toggle. Twin of
 * web-next/src/components/SimMoreNote.tsx.
 */
export function SimMoreNote({ children, testID, style }: { children: ReactNode; testID?: string; style?: StyleProp<TextStyle> }) {
  const { colors } = useThemeMode();
  const [open, setOpen] = useState(false);
  return (
    <Pressable onPress={() => setOpen((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: open }} testID={testID} hitSlop={6}>
      <AppText style={[styles.text, { color: colors.textSecondary }, style]} numberOfLines={open ? undefined : 1}>
        {children}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({ text: { fontSize: 13, lineHeight: 18 } });
