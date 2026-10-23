import React from 'react';
import { Switch } from 'react-native';

import { useThemeMode } from '../context/ThemeModeContext';

/**
 * The one switch: the native Switch with theme track colors. `tone` picks the
 * on-state lane (accent by default, danger for opt-outs, premium for the
 * founder-only Privacy mode). Mirrors web-next's components/Toggle.tsx.
 */
export default function Toggle({
  value,
  onValueChange,
  disabled = false,
  label,
  tone = 'accent',
}: {
  value: boolean;
  onValueChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
  tone?: 'accent' | 'danger' | 'premium';
}) {
  const { colors } = useThemeMode();
  const on = tone === 'danger' ? colors.danger : tone === 'premium' ? colors.premium : colors.accent;
  return (
    <Switch
      value={value}
      onValueChange={onValueChange}
      disabled={disabled}
      accessibilityLabel={label}
      trackColor={{ true: on, false: colors.border }}
    />
  );
}
