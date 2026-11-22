import React from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import SegmentedTabBar from './SegmentedTabBar';
import { CONNECT_MODES, type ConnectMode } from '../lib/connectFlow';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing } from '../theme';

/**
 * The connect step's three ways in: connect a league (default), look around a sample league, or play Fantasy Sim
 * (needs no league). Same options and copy as web's ConnectModeTabs (lib/connectFlow.ts CONNECT_MODES).
 */
export function ConnectModeTabs({ mode, onChange }: { mode: ConnectMode; onChange: (mode: ConnectMode) => void }) {
  return (
    <View style={styles.tabs}>
      <SegmentedTabBar<ConnectMode>
        options={CONNECT_MODES.map((m) => ({ key: m.key, label: m.label }))}
        active={mode}
        onChange={onChange}
      />
    </View>
  );
}

/** The Sample / Sim panel under the tabs (the Connect panel is the screen's own add-league card). */
export function ConnectModePanel({ mode, onSample, onSim }: { mode: Exclude<ConnectMode, 'connect'>; onSample: () => void; onSim: () => void }) {
  const { colors } = useThemeMode();
  const current = CONNECT_MODES.find((m) => m.key === mode)!;
  return (
    <View style={styles.panel}>
      <AppText style={{ fontSize: 14, lineHeight: 20, color: colors.textSecondary }}>{current.blurb}</AppText>
      <Button label={current.action} variant="primary" onPress={mode === 'sample' ? onSample : onSim} />
    </View>
  );
}

const styles = StyleSheet.create({
  tabs: { marginBottom: spacing.md },
  panel: { gap: spacing.md },
});
