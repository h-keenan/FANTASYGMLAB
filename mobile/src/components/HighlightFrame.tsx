import React, { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii } from '../theme';

/**
 * App equivalent of web-next's HighlightTarget: marks the one row a deep link
 * (Waivers `playerId`) named with an accent outline. Renders children
 * untouched when `active` is false. `onReveal` gets the frame's window-space
 * top so the owning list can scroll it into view.
 */
export default function HighlightFrame({
  active,
  onReveal,
  children,
}: {
  active: boolean;
  onReveal?: (windowY: number) => void;
  children: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const ref = useRef<View>(null);
  useEffect(() => {
    if (!active || !onReveal) return;
    const t = setTimeout(() => {
      ref.current?.measureInWindow((_x, y) => onReveal(y));
    }, 300);
    return () => clearTimeout(t);
  }, [active, onReveal]);
  return (
    <View
      ref={ref}
      collapsable={false}
      style={active ? [styles.frame, { borderColor: colors.accent }] : undefined}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: { borderWidth: 2, borderRadius: radii.lg, padding: 2 },
});
