import React, { useEffect, useMemo, useRef } from 'react';
import { StyleSheet, View } from 'react-native';

import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import { haptic } from '../lib/haptic';
import { selectionActionLabel } from '../lib/bottomNav';
import { useOrbClearance } from '../lib/orbLayout';
import { spacing, type ThemeColors } from '../theme';

/**
 * Selection mode for a pick-from-a-list + submit screen in the site shell (the app's footer there is the GM orb zone, not
 * the Sim pill): ONE sticky action, "3 selected · Find trades", a flex sibling BELOW the list so the list ends above it and
 * no row is covered, padded by the orb clearance so it never sits under the orb. Renders nothing at zero selected (the
 * screen then pads its list by `useOrbClearance` as usual). Inside the Fantasy Sim the same action goes through the pill
 * (`selectionPrimary` in lib/bottomNav.ts) instead; never both. Guard: scripts/check_selection_submit.mjs.
 * Web twin: the footer primary (selectionPrimary + TradesTabBar `primary`).
 */
export default function SelectionActionBar({ count, verb, busy = false, disabled = false, onPress }: { count: number; verb: string; busy?: boolean; disabled?: boolean; onPress: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const orbClearance = useOrbClearance();
  const prev = useRef(0);
  useEffect(() => {
    if (count !== prev.current && count > 0) haptic('select');
    prev.current = count;
  }, [count]);
  if (!(count > 0)) return null;
  return (
    <View style={[styles.bar, { paddingBottom: orbClearance + spacing.sm }]} testID="selection-action-bar">
      <Button label={selectionActionLabel(count, verb)} loading={busy} disabled={disabled} onPress={onPress} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    bar: {
      backgroundColor: colors.glass,
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopColor: colors.glassBorder,
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.sm,
    },
  });
}
