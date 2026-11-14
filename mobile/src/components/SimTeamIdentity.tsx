import React, { useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import SimCrest from './SimCrest';
import { useThemeMode } from '../context/ThemeModeContext';
import { SIM_TEAM_SIZES, simTeamNameFit, type SimTeamSize } from '../lib/simTeamIdentity';

/**
 * The generated team logo at a slot from the size table (lib/simTeamIdentity.ts: inline 16 / chip 20 / row 28 / card 44 / hero 56 /
 * sheet 72). The ONLY place a sim component may mount SimCrest (guarded by lib/simTeamIdentityRule.test.ts). Mirrors web-next.
 */
export function SimTeamLogo({ name, size = 'row', label = false }: { name: string; size?: SimTeamSize; label?: boolean }) {
  return <SimCrest name={name} size={SIM_TEAM_SIZES[size]} label={label} />;
}

/**
 * THE way a Fantasy Sim team is shown: logo + name. The name is never ellipsized and never cut mid-word: it walks the fit
 * ladder (full name, wrapped to two lines, one font step smaller). `stacked` = logo above a centered name; `hideName` = logo only.
 */
export function SimTeamIdentity({
  name,
  size = 'row',
  stacked = false,
  isYou = false,
  suffix,
  bold = true,
  hideName = false,
  fontSize = 15,
}: {
  name: string;
  size?: SimTeamSize;
  stacked?: boolean;
  isYou?: boolean;
  suffix?: ReactNode;
  bold?: boolean;
  hideName?: boolean;
  fontSize?: number;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const fit = simTeamNameFit(name, stacked);
  return (
    <View style={stacked ? styles.stacked : styles.row}>
      <SimTeamLogo name={name} size={size} />
      {hideName ? null : (
        <AppText
          style={[styles.name, { fontSize: fontSize * fit.scale }, !bold && styles.light, stacked && styles.center]}
          testID="sim-team-name"
        >
          {name}
          {isYou ? ' (you)' : ''}
        </AppText>
      )}
      {suffix}
    </View>
  );
}

const createStyles = (colors: { textPrimary: string }) =>
  StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: 8, flexShrink: 1, minWidth: 0 },
    stacked: { alignItems: 'center', justifyContent: 'center', gap: 4, flexShrink: 1, minWidth: 0 },
    name: { fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    light: { fontWeight: '500' },
    center: { textAlign: 'center' },
  });
